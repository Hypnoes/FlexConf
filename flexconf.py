"""FlexConf reference implementation.

FlexConf has a single unified structural model (Language SPEC: Block
Structure): every document is tokenized into four structural tokens —
LBRACE, RBRACE, KVSEP, ITEMSEP — each realized either by a literal string or
by a line-structure event (Language SPEC: Structural Tokens and Realizers).
Two named styles, BRACE (default) and INDENT, are predefined. Comments are
introduced by '#'.

The lexer picks one candidate per position: the longest match wins, and on a
tie a realizer beats the bare lexical run. The parser consumes the four tokens
and never inspects the realizer.

Pipeline: Lexer (pragma scan -> surface selection -> tokenize)
-> Parser (unified block parsing) -> Interpreter (native types).
"""

import re
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from enum import Enum, auto
from math import gcd
from typing import Any

# --- Configuration & Constants ---

# Event realizer spellings (Language SPEC: Structural Tokens and Realizers).
# These denote tokens generated from line-structure analysis, not literal text.
INDENT = '<INDENT>'    # one indentation level deeper   (virtual LBRACE)
DEDENT = '<DEDENT>'    # one indentation level shallower (virtual RBRACE)
NEWLINE = '<NEWLINE>'  # line ending                    (virtual ITEMSEP)

SYMBOLIC_VALUES = (INDENT, DEDENT, NEWLINE)

# Comments start with '#' and run to the end of the line
# (Language SPEC: Comments).
COMMENT_MARKER = '#'

# The date/time sigil is fixed meta-syntax (Language SPEC: Dates and Times),
# like the '#?>' pragma prefix: it never changes with the syntax parameters,
# and no literal parameter value may contain it.
DATETIME_SIGIL = '@'

# '!' is reserved meta-syntax (Language SPEC: Reserved Words and Symbols).
# It currently has no production, so outside a string it is always a
# SyntaxError; nothing may bind it as a parameter value either.
RESERVED_SIGIL = '!'

# Symbols that no literal syntax-parameter value may contain, paired with the
# reason used in diagnostics.
RESERVED_IN_PARAMS = ((DATETIME_SIGIL, 'reserved for date/time literals'),
                      (RESERVED_SIGIL, 'reserved for future use'))

# The character class of a bare lexical run: the characters § Keys allows for
# bare identifiers, together with the characters the number productions may
# consume (sign, fraction point). It is fixed and independent of the effective
# surface (Language SPEC: Lexical Boundaries).
BARE_RUN_CHARS = frozenset(
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    '_-+.'
)

# RFC 3339 profile (ABNF SPEC: Date and Time Types). '@' is not part of the
# captured body. The date-time separator may be 'T', 't', or exactly one
# space (RFC 3339 §5.6 readability form); lowercase 'z' is accepted too. The
# separator is normalized away before parsing (the body is rebuilt with 'T').
_DATETIME_RE = re.compile(
    r'@(?:'
    r'(?P<date>\d{4}-\d{2}-\d{2})'
    r'(?:[Tt\x20](?P<time>\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    r'(?P<offset>[Zz]|[+-]\d{2}:\d{2})?)?'
    r'|(?P<timeonly>\d{2}:\d{2}:\d{2}(?:\.\d+)?))'
)


def _parse_datetime_body(m: re.Match):
    """Convert a _DATETIME_RE match to a date/time/datetime object.

    Raises ValueError on calendar-invalid values (e.g. month 13, Feb 30).
    Requires Python 3.11+ (fromisoformat accepts 'Z' and arbitrary-length
    fractional seconds, truncated to microseconds).
    """
    if m.group('timeonly') is not None:
        return time.fromisoformat(m.group('timeonly'))
    d = m.group('date')
    if m.group('time') is None:
        return date.fromisoformat(d)
    body = f"{d}T{m.group('time')}"
    offset = m.group('offset')
    if offset:
        body += 'Z' if offset in ('Z', 'z') else offset
    return datetime.fromisoformat(body)

# Pragma token names -> Config fields (Language SPEC: Pragma Directives)
PARAM_FIELDS = {
    'KVSEP': 'key_value_separator',
    'ITEMSEP': 'item_separator',
    'LBRACE': 'left_brace',
    'RBRACE': 'right_brace',
}

STYLE_PRESETS = {
    'BRACE': dict(key_value_separator=':', item_separator=',',
                  left_brace='{', right_brace='}'),
    'INDENT': dict(key_value_separator=':', item_separator=NEWLINE,
                   left_brace=INDENT, right_brace=DEDENT),
}


class FlexConfError(Exception):
    def __init__(self, message, line, col):
        self.message = message
        super().__init__(f"{message} at line {line}, column {col}")


@dataclass(frozen=True)
class Config:
    """Effective syntax configuration of a document (Parser SPEC 7).

    The defaults are the BRACE style. Use Config.style_indent() for the
    INDENT preset; both accept field overrides, e.g.
    Config.style_indent(key_value_separator='=').

    Validation (Language SPEC: Structural Tokens and Realizers) runs at construction:
    conflicting or otherwise illegal configurations raise FlexConfError
    before any parsing takes place.
    """
    key_value_separator: str = ':'
    item_separator: str = ','
    left_brace: str = '{'
    right_brace: str = '}'

    @classmethod
    def style_brace(cls, **overrides):
        return replace(cls(), **overrides)

    @classmethod
    def style_indent(cls, **overrides):
        return replace(cls(item_separator=NEWLINE,
                           left_brace=INDENT, right_brace=DEDENT),
                       **overrides)

    def __post_init__(self):
        def fail(msg):
            raise FlexConfError(f"Invalid surface: {msg}", 1, 1)

        kv, sep, lb, rb = (self.key_value_separator, self.item_separator,
                           self.left_brace, self.right_brace)

        # Symbolic value placement (Language SPEC: Structural Tokens and Realizers)
        if kv in SYMBOLIC_VALUES:
            fail("KVSEP must be a literal string")
        if sep in (INDENT, DEDENT):
            fail(f"ITEMSEP cannot be bound to '{sep}'")
        if lb in (DEDENT, NEWLINE):
            fail(f"LBRACE cannot be bound to '{lb}'")
        if rb in (INDENT, NEWLINE):
            fail(f"RBRACE cannot be bound to '{rb}'")
        if (lb == INDENT) != (rb == DEDENT):
            fail("<INDENT>/<DEDENT> must be bound as a pair to "
                 "LBRACE/RBRACE")

        # Literal realizers: pairwise distinct, and never the comment marker
        literals = {'KVSEP': kv}
        if sep != NEWLINE:
            literals['ITEMSEP'] = sep
        if lb != INDENT:
            literals['LBRACE'] = lb
            literals['RBRACE'] = rb

        seen = []
        for name, v in literals.items():
            if not v:
                fail(f"{name} must not be empty")
            if any(c.isspace() for c in v):
                fail(f"{name} must not contain whitespace")
            if any(q in v for q in '"\'`'):
                fail(f"{name} must not contain string quote characters")
            for sigil, why in RESERVED_IN_PARAMS:
                if sigil in v:
                    fail(f"{name} must not contain {sigil!r} ({why})")
            for other_name, other in seen:
                if v == other:
                    fail(f"{name} {v!r} and {other_name} {other!r} are the "
                         "same literal realizer")
            if v.startswith(COMMENT_MARKER) or COMMENT_MARKER.startswith(v):
                fail(f"{name} {v!r} conflicts with the comment marker "
                     f"{COMMENT_MARKER!r}")
            seen.append((name, v))

        # Reference-implementation limit (the SPEC allows this combination,
        # but blank-line separation of anonymous map items is only defined
        # for ITEMSEP=<NEWLINE>, which this implementation requires).
        if lb == INDENT and sep != NEWLINE:
            fail("this implementation requires ITEMSEP=<NEWLINE> "
                 "when LBRACE=<INDENT> (the INDENT style)")


class TokenType(Enum):
    # Primitives
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()
    DATETIME = auto()      # '@'-sigiled date/time literal
    IDENTIFIER = auto()

    # Structural tokens (Language SPEC: Structural Tokens and Realizers). Each
    # is realized by a literal string or by a line-structure event; the lexer
    # emits the token, never the realizer.
    LBRACE = auto()
    RBRACE = auto()
    KVSEP = auto()
    ITEMSEP = auto()

    EOF = auto()


class Token:
    def __init__(self, token_type: TokenType, value: Any, line: int, col: int):
        self.type = token_type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)}, line={self.line})"


# --- Lexer ---

class Lexer:
    def __init__(self, text: str, config: Config = None):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.indent_stack = [0]

        # Configuration (Parser SPEC 7): an explicit Config argument becomes
        # the base; pragma directives at the file head then apply on top.
        self._explicit_config = config is not None
        base = config if config is not None else Config()
        self.config, self.has_pragmas, self.pragma_end = self._scan_pragmas(base)
        self.mode = self._detect_mode()

    # -- Pragmas ----------------------------------------------------------

    def _scan_pragmas(self, base: Config):
        # Pragma directives (#?>) are fixed meta-syntax: they are recognized
        # before the configuration takes effect (Language SPEC: Pragma
        # Directives). They form one contiguous block at the very start of
        # the document; only whitespace, blank lines, and '#' comments may
        # precede the block, and the first line that is not a pragma line
        # ends it. A '#?>' line outside the block is a SyntaxError, which
        # _skip_comment() raises when tokenization reaches it.
        values = {field: getattr(base, field) for field in PARAM_FIELDS.values()}
        pos = 0
        last_line = 1
        found = False
        for raw_line in self.text.split('\n'):
            stripped = raw_line.strip()
            line_end = pos + len(raw_line) + 1  # +1 for the '\n'
            is_pragma = stripped.startswith('#?>')
            if found:
                if not is_pragma:
                    break  # the pragma block is contiguous
            elif not (is_pragma or not stripped or stripped.startswith('#')):
                break  # data begins before any pragma
            if is_pragma:
                last_line = self.text.count('\n', 0, pos) + 1
                self._apply_pragma(stripped[len('#?>'):].strip(), values, last_line)
                found = True
            pos = line_end
        try:
            config = replace(base, **values)
        except FlexConfError as e:
            raise FlexConfError(e.message, last_line, 1) from e
        return config, found, pos

    def _apply_pragma(self, body: str, values: dict, line: int):
        parts = body.split(None, 2)
        if len(parts) < 3 or parts[0] != 'SET':
            raise FlexConfError("Malformed pragma (expected '#?> SET ...')", line, 1)
        target, arg = parts[1], parts[2].strip()
        if target == 'STYLE':
            preset = STYLE_PRESETS.get(arg)
            if preset is None:
                raise FlexConfError(f"Unknown style '{arg}'", line, 1)
            values.update(preset)
        elif target in PARAM_FIELDS:
            values[PARAM_FIELDS[target]] = self._parse_pragma_value(arg, line)
        else:
            raise FlexConfError(f"Unknown pragma token '{target}'", line, 1)

    def _parse_pragma_value(self, arg: str, line: int):
        if arg.startswith('<') and arg.endswith('>'):
            if arg in SYMBOLIC_VALUES:
                return arg
            raise FlexConfError(f"Unknown symbolic value '{arg}'", line, 1)
        if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in ('"', "'"):
            return arg[1:-1]
        raise FlexConfError(
            "Pragma value must be a quoted string or a symbolic value "
            "(<INDENT>/<DEDENT>/<NEWLINE>)", line, 1)

    # -- Surface detection --------------------------------------------------

    def _detect_mode(self):
        # Style resolution & surface detection (Parser SPEC 3.2).
        p = self.pragma_end
        while p < len(self.text):
            char = self.text[p]
            if char.isspace():
                p += 1
                continue
            if char == COMMENT_MARKER:
                while p < len(self.text) and self.text[p] != '\n':
                    p += 1
                continue
            break

        if self.config.left_brace == INDENT:
            return 'indentation'
        if p < len(self.text):
            winner = self._winning_candidate(p)
            if winner is not None and winner[1] == TokenType.LBRACE:
                return 'bracket'
        if p >= len(self.text):
            return 'indentation'  # Default empty file
        if not self.has_pragmas and not self._explicit_config:
            # Backward-compatible auto-detection (Language SPEC: Style
            # Resolution): no pragmas, default config, non-brace document.
            self.config = Config.style_indent()
            return 'indentation'
        line = self.text.count('\n', 0, p) + 1
        col = p - self.text.rfind('\n', 0, p)
        raise FlexConfError(
            f"Document does not start with LBRACE {self.config.left_brace!r}; "
            "use '#?> SET STYLE INDENT' for the indentation surface", line, col)

    # -- Tokenization -------------------------------------------------------

    def _winning_candidate(self, p):
        """The candidate that wins the match at p, or None.

        Candidates are every literal realizer that matches at p and the bare
        lexical run that begins there; the longest wins, and on a tie a realizer
        beats the bare run (Language SPEC: Matching Order). Returns
        (length, token type, value).
        """
        candidates = []  # (length, priority, token type, value)
        for literal, token_type in self._literal_realizers():
            if self.text.startswith(literal, p):
                candidates.append((len(literal), 1, token_type, literal))

        run = self._bare_run_at(p)
        if run:
            type_, value = self._classify_literal(run)
            candidates.append((len(run), 0, type_, value))

        if not candidates:
            return None
        candidates.sort(key=lambda c: (-c[0], -c[1]))
        length, _, token_type, value = candidates[0]
        return length, token_type, value

    def _bare_run_at(self, p) -> str:
        # The longest run of bare-run characters starting at p.
        q = p
        while q < len(self.text) and self.text[q] in BARE_RUN_CHARS:
            q += 1
        return self.text[p:q]

    def _realizer_wins_at(self, p) -> bool:
        # True when a structural token — a realizer — wins the match at p, which
        # is what makes p a structural delimiter for a date/time literal.
        winner = self._winning_candidate(p)
        return winner is not None and winner[1] in (TokenType.LBRACE,
                                                    TokenType.RBRACE,
                                                    TokenType.KVSEP,
                                                    TokenType.ITEMSEP)

    def _literal_realizers(self):
        # The literal realizers of the effective surface, as (literal, token)
        # pairs. Symbolic realizers produce their token from line structure
        # instead and are never matched as literal text (Language SPEC:
        # Structural Tokens and Realizers).
        cfg = self.config
        for literal, token_type in ((cfg.left_brace, TokenType.LBRACE),
                                    (cfg.right_brace, TokenType.RBRACE),
                                    (cfg.key_value_separator, TokenType.KVSEP),
                                    (cfg.item_separator, TokenType.ITEMSEP)):
            if literal not in SYMBOLIC_VALUES:
                yield literal, token_type

    def _compute_base_indent_unit(self):
        # Base indent unit = GCD of all non-zero indentation widths
        # (Language SPEC: INDENT style). Blank and comment-only lines excluded.
        base = None
        for line in self.text.split('\n'):
            content = line.lstrip(' ')
            if not content.strip():
                continue  # blank line
            if content.startswith(COMMENT_MARKER):
                continue  # comment-only line
            indent = len(line) - len(content)
            if indent > 0:
                base = indent if base is None else gcd(base, indent)
        return base

    def tokenize(self) -> list[Token]:
        self.tokens = []
        self.indent_stack = [0]
        self.base_indent_unit = self._compute_base_indent_unit()

        # Skip the pragma block: it was already consumed by _scan_pragmas.
        self.pos = self.pragma_end
        self.line = self.text.count('\n', 0, self.pragma_end) + 1
        self.col = self.pragma_end - self.text.rfind('\n', 0, self.pragma_end)

        # Handle initial indentation/content for the indentation surface
        if self.mode == 'indentation':
            self._handle_indentation()

        while self.pos < len(self.text):
            char = self.text[self.pos]

            # 1. Line structure (Language SPEC: Whitespace Handling). A line
            #    ending realizes ITEMSEP when the surface binds it that way, and
            #    in the indentation surface it also feeds the block realizer.
            if char == '\n':
                self._advance()
                if self.config.item_separator == NEWLINE:
                    self.tokens.append(Token(TokenType.ITEMSEP, '\n', self.line - 1, self.col))
                if self.mode == 'indentation':
                    self._handle_indentation()
                continue

            if char.isspace():
                self._advance()
                continue

            # 2. Handle Comments ('#' to end of line)
            if char == COMMENT_MARKER:
                self._skip_comment()
                continue

            # 3. Reserved meta-syntax with no production. '@' is handled by
            #    _match_token below (the date/time sigil); '!' currently has no
            #    meaning, so it is an error outside a string.
            if char == RESERVED_SIGIL:
                raise FlexConfError(
                    f"{RESERVED_SIGIL!r} is reserved meta-syntax and may not "
                    "appear bare outside a string; quote it to use it as data",
                    self.line, self.col)

            # 4. One match wins (Language SPEC: Matching Order)
            if self._match_token():
                continue

            raise FlexConfError(self._unexpected_char_message(char),
                                self.line, self.col)

        # EOF Handling
        if self.mode == 'indentation':
            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.RBRACE, None, self.line, self.col))

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return self.tokens

    def _startswith(self, s: str) -> bool:
        return self.text.startswith(s, self.pos)

    def _match_token(self) -> bool:
        """Match one token at the current position.

        Every realizer that matches here and the bare lexical run that begins
        here are candidates; the longest wins, and on a tie a realizer beats the
        bare run (Language SPEC: Matching Order). A literal realizer is
        therefore never matched inside a bare run, and prefix relations between
        realizers need no special rule.
        """
        char = self.text[self.pos]

        # Reserved symbols with atomic literals. No realizer may begin with one
        # of these characters (Language SPEC: Literal realizers).
        if char in ('"', "'"):
            self.tokens.append(self._match_string())
            return True
        if char == DATETIME_SIGIL:
            self.tokens.append(self._match_datetime())
            return True

        winner = self._winning_candidate(self.pos)
        if winner is None:
            return False
        length, token_type, value = winner
        self.tokens.append(Token(token_type, value, self.line, self.col))
        self._advance(length)
        return True

    def _unexpected_char_message(self, char: str) -> str:
        # A character consumed by no token is not data (Parser SPEC 4.3).
        message = f"Unexpected character '{char}'"
        if char in '{}[]' and self.mode == 'indentation':
            message += (" — no token consumes it; bind it as a literal "
                        "realizer or use the BRACE style")
        return message

    def _flush_blanks(self, n):
        # A blank line realizes an extra ITEMSEP token (Parser SPEC 3.4)
        for _ in range(n):
            self.tokens.append(Token(TokenType.ITEMSEP, '\n', self.line, 1))

    def _handle_indentation(self):
        # Event token generation (Parser SPEC 3.4): consumes whitespace/
        # comments/newlines until a real line starts, then emits one LBRACE or
        # RBRACE per indentation level. Blank lines are buffered; when they
        # precede a dedent, they are emitted AFTER the RBRACE tokens (together
        # with the moved line-end ITEMSEP), so a blank line stays visible at the
        # level whose items it separates (anonymous maps, Parser SPEC 4.2).

        pending_blanks = 0
        while self.pos < len(self.text):
            # Peek at current line indentation
            spaces = 0
            p = self.pos
            while p < len(self.text):
                c = self.text[p]
                if c == ' ':
                    spaces += 1
                    p += 1
                elif c == '\t':
                    raise FlexConfError("Tabs not allowed", self.line, self.col)
                else:
                    break

            # Check what follows
            if p >= len(self.text):
                break

            c = self.text[p]
            if c == '\n':
                # Blank line: buffer it until the next indentation is known
                self._advance(p - self.pos + 1)  # Consume spaces + newline
                pending_blanks += 1
                continue
            elif self.text[p] == COMMENT_MARKER:
                # Comment line, ignore (generates no tokens)
                self._advance(p - self.pos)  # Consume spaces
                self._skip_comment()
                # After comment, we might have newline, loop again
                if self.pos < len(self.text) and self.text[self.pos] == '\n':
                    self._advance()
                    continue
                break
            else:
                # Real content found
                self._advance(p - self.pos)  # Consume the spaces
                indent_len = spaces

                # Base unit was precomputed from the whole document
                if self.base_indent_unit and indent_len > 0 and indent_len % self.base_indent_unit != 0:
                    raise FlexConfError("Indentation not a multiple of base unit", self.line, self.col)

                current_level = self.indent_stack[-1]
                if indent_len > current_level:
                    self._flush_blanks(pending_blanks)
                    # One LBRACE per indentation level (Parser SPEC 3.4), so
                    # the parser can detect the extra level of anonymous map
                    # items inside lists.
                    base = self.base_indent_unit or indent_len
                    level = current_level + base
                    while level < indent_len:
                        self.indent_stack.append(level)
                        self.tokens.append(Token(TokenType.LBRACE, None, self.line, self.col))
                        level += base
                    self.indent_stack.append(indent_len)
                    self.tokens.append(Token(TokenType.LBRACE, None, self.line, self.col))
                elif indent_len < current_level:
                    # Move the preceding line-end ITEMSEP past the RBRACEs so
                    # the enclosing level sees it (and any blank lines).
                    moved_sep = None
                    if self.tokens and self.tokens[-1].type == TokenType.ITEMSEP:
                        moved_sep = self.tokens.pop()
                    while indent_len < current_level:
                        self.indent_stack.pop()
                        current_level = self.indent_stack[-1]
                        self.tokens.append(Token(TokenType.RBRACE, None, self.line, self.col))
                    if indent_len != current_level:
                        raise FlexConfError("Unindent does not match any outer indentation level", self.line, self.col)
                    if moved_sep is not None:
                        self.tokens.append(moved_sep)
                    self._flush_blanks(pending_blanks)
                else:
                    self._flush_blanks(pending_blanks)

                return

        # Trailing blank lines at end of file
        self._flush_blanks(pending_blanks)

    def _advance(self, n=1):
        for _ in range(n):
            if self.pos < len(self.text):
                if self.text[self.pos] == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                self.pos += 1

    def _skip_comment(self):
        # The head pragma block was consumed before tokenization, so a '#?>'
        # reached here is outside the block: it is reserved meta-syntax and
        # must not be silently treated as a comment (Language SPEC: Pragma
        # Directives).
        if self.text.startswith('#?>', self.pos):
            raise FlexConfError(
                "'#?>' pragma directives must form a contiguous block at the "
                "beginning of the document", self.line, self.col)
        while self.pos < len(self.text) and self.text[self.pos] != '\n':
            self._advance()

    def _match_string(self):
        # Simple string parser (does not handle all escapes/multiline
        # perfectly in this ref)
        quote = self.text[self.pos]
        end_quote = self.text.find(quote, self.pos + 1)
        if end_quote == -1:
            raise FlexConfError("Unterminated string", self.line, self.col)
        val = self.text[self.pos + 1:end_quote]
        token = Token(TokenType.STRING, val, self.line, self.col)
        self._advance(end_quote - self.pos + 1)
        return token

    def _match_datetime(self):
        """Scan a '@'-sigiled date/time literal (Language SPEC: Dates and
        Times). The body must match the RFC 3339 profile and be followed by a
        structural delimiter — a token that a realizer wins at that position —
        or by whitespace, a comment, or EOF; any other '@' outside a string is
        a SyntaxError."""
        m = _DATETIME_RE.match(self.text, self.pos)
        end = m.end() if m else -1
        if m and (end == len(self.text)
                  or self.text[end].isspace()
                  or self.text[end] == COMMENT_MARKER
                  or self._realizer_wins_at(end)):
            raw = m.group(0)
            try:
                val = _parse_datetime_body(m)
            except ValueError as e:
                raise FlexConfError(
                    f"Invalid date/time literal {raw!r}: {e}",
                    self.line, self.col)
            token = Token(TokenType.DATETIME, val, self.line, self.col)
            self._advance(len(raw))
            return token
        raise FlexConfError(
            "'@' must introduce a well-formed date/time literal "
            "(e.g. @1979-05-27T07:32:00Z, @1979-05-27, @07:32:00)",
            self.line, self.col)

    def _classify_literal(self, raw):
        if raw == 'true':
            return TokenType.BOOLEAN, True
        if raw == 'false':
            return TokenType.BOOLEAN, False
        if raw == 'null':
            return TokenType.NULL, None

        # Special floats (Language SPEC: Numbers): inf / nan, optionally
        # signed, lower case. float() accepts the sign forms directly.
        if raw.lstrip('+-') in ('inf', 'nan'):
            return TokenType.NUMBER, float(raw)

        # Number
        try:
            if '.' in raw or 'e' in raw.lower():
                return TokenType.NUMBER, float(raw)
            return TokenType.NUMBER, int(raw)
        except ValueError:
            pass

        # Identifier
        return TokenType.IDENTIFIER, raw


# --- AST (IR) ---

class Node:
    """Base class for AST nodes. Every node carries source position info."""

    def __init__(self, line: int, col: int):
        self.line = line
        self.col = col


class ScalarNode(Node):
    """A primitive value: string, number, boolean, or null."""

    def __init__(self, value: Any, line: int, col: int):
        super().__init__(line, col)
        self.value = value

    def __repr__(self):
        return f"ScalarNode({self.value!r}, line={self.line})"


class MapNode(Node):
    """A map: string keys (insertion-ordered) to child nodes.

    Keys are stringified at parse time, so digit-leading bare keys such as
    `0:` appear here as '0' (Language SPEC: Keys).
    """

    def __init__(self, entries: dict, line: int, col: int):
        super().__init__(line, col)
        self.entries = entries  # dict[str, Node]

    def __repr__(self):
        return f"MapNode({list(self.entries)}, line={self.line})"


class ListNode(Node):
    """An anonymous map (Language SPEC: Anonymous Maps), realized directly
    as an ordered sequence of child nodes.

    The implicit string keys "0", "1", "2", ... of the semantic model are
    never materialized: the key of an element is simply the decimal string
    of its index. This is the construction route recommended by
    Parser SPEC 5.2. Anonymous map items in the indentation surface are
    plain MapNode elements here.
    """

    def __init__(self, elements: list, line: int, col: int):
        super().__init__(line, col)
        self.elements = elements  # list[Node]

    def __repr__(self):
        return f"ListNode({len(self.elements)} items, line={self.line})"


# --- Parser ---

class Parser:
    """Surface-agnostic block parser (Parser SPEC 4).

    The lexer emits the four structural tokens whatever realizes them
    (Language SPEC: Structural Tokens and Realizers), so one block-parsing
    procedure handles every surface. Only the anonymous-map-of-maps rule needs
    to know whether the block realizer is an event: an event realizer wraps the
    map level, while a literal one opens each item with its own LBRACE.
    """

    def __init__(self, tokens: list[Token], config: Config):
        self.tokens = tokens
        self.pos = 0
        self.item_sep = TokenType.ITEMSEP
        self.event_braces = config.left_brace == INDENT

    def peek(self, offset=0) -> Token:
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return self.tokens[-1]  # EOF

    def consume(self, type_: TokenType = None):
        token = self.peek()
        if type_ and token.type != type_:
            raise FlexConfError(f"Expected {type_.name}, got {token.type.name}", token.line, token.col)
        self.pos += 1
        return token

    def parse(self):
        # Unified entry: a leading LBRACE opens an explicit root block;
        # otherwise the document is an implicit root block whose braces are
        # the start and end of the document (Parser SPEC 4.2).
        first = self.peek()
        if first.type == TokenType.LBRACE:
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, self.item_sep)
        return self._parse_items(TokenType.EOF, self.item_sep)

    def _parse_block(self, start_token, end_token, separator_token):
        start = self.consume(start_token)

        # Two consecutive LBRACEs open an anonymous map whose map items sit one
        # level deeper (Parser SPEC 4.2). An event block realizer wraps the
        # whole list, so it needs the dedicated routine; with a literal realizer
        # each item carries its own LBRACE and the generic item parser already
        # handles the nesting.
        if (start_token == TokenType.LBRACE and self.event_braces
                and self.peek().type == TokenType.LBRACE):
            self.consume()
            return self._parse_list_block(start.line, start.col)

        # Check if empty block
        if self.peek().type == end_token:
            self.consume()
            return MapNode({}, start.line, start.col)  # Default to empty map

        result = self._parse_items(end_token, separator_token)
        self.consume(end_token)
        return result

    def _parse_list_block(self, line, col):
        # Anonymous map whose items are anonymous maps (at the deeper level,
        # separated by exactly one blank line) and/or scalars (at the list
        # level).
        elements = []

        # Anonymous map items at the deeper level
        while True:
            self._skip_separators()
            if self.peek().type in (TokenType.RBRACE, TokenType.EOF):
                break
            elements.append(self._parse_anonymous_map())

        self.consume(TokenType.RBRACE)  # map level -> list level

        # Scalar items at the list level
        while self.peek().type not in (TokenType.RBRACE, TokenType.EOF):
            if self.peek().type == TokenType.ITEMSEP:
                self.consume()
                continue
            elements.append(self._parse_value())

        self.consume(TokenType.RBRACE)  # list level -> enclosing level
        return ListNode(elements, line, col)

    def _parse_anonymous_map(self):
        # Anonymous map inside a list: key-value pairs at the same level,
        # ended by a blank line (two consecutive ITEMSEPs) or by RBRACE.
        start = self.peek()
        res = {}
        while True:
            t = self.peek()
            if t.type in (TokenType.RBRACE, TokenType.EOF):
                break
            if t.type == TokenType.ITEMSEP:
                if self.peek(1).type in (TokenType.ITEMSEP, TokenType.RBRACE, TokenType.EOF):
                    break  # blank line ends this map item
                self.consume()
                continue
            key_token = self.peek()
            key = self._parse_key()
            self.consume(TokenType.KVSEP)
            val = self._parse_value()
            if key in res:
                raise FlexConfError(f"Duplicate key '{key}'", key_token.line, key_token.col)
            res[key] = val
        return MapNode(res, start.line, start.col)

    def _skip_separators(self):
        while self.peek().type == TokenType.ITEMSEP:
            self.consume()

    def _parse_items(self, end_token, separator_token):
        # Generic item parser for both Map and anonymous Map content.
        # Sniff the first item to decide which it is (Parser SPEC 4.2):
        # an item written with a key makes the block a Map, an item without
        # one makes it an anonymous Map — the item FORM decides, never the
        # key values.

        self._skip_separators()  # tolerate leading blank lines
        is_map = self._is_map_entry()

        if is_map:
            return self._finish_map(end_token, separator_token)
        else:
            return self._finish_list(end_token, separator_token)

    def _finish_map(self, end_token, separator_token):
        start = self.peek()
        res = {}
        while self.peek().type != end_token and self.peek().type != TokenType.EOF:
            if self.peek().type == separator_token:
                self.consume()
                continue

            key_token = self.peek()
            key = self._parse_key()
            self.consume(TokenType.KVSEP)
            val = self._parse_value()
            if key in res:
                raise FlexConfError(f"Duplicate key '{key}'", key_token.line, key_token.col)
            res[key] = val

            if self.peek().type == separator_token:
                self.consume()
            elif self.peek().type != end_token:
                # The Language SPEC requires an ITEMSEP between items;
                # the reference parser is lenient here and lets the next
                # loop iteration continue the parse.
                pass
            else:
                break
        return MapNode(res, start.line, start.col)

    def _finish_list(self, end_token, separator_token):
        start = self.peek()
        res = []
        while self.peek().type != end_token and self.peek().type != TokenType.EOF:
            if self.peek().type == separator_token:
                self.consume()
                continue

            val = self._parse_value()
            res.append(val)

            if self.peek().type == separator_token:
                self.consume()
            elif self.peek().type != end_token:
                pass
            else:
                break
        return ListNode(res, start.line, start.col)

    def _parse_value(self):
        t = self.peek()

        # A block: an LBRACE, whether literal or produced by the realizer
        if t.type == TokenType.LBRACE:
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, self.item_sep)

        # ... or, in the indentation surface, the line ending that realizes
        # ITEMSEP immediately before the block's LBRACE.
        if t.type == TokenType.ITEMSEP and self.event_braces:
            self.consume()
            self._skip_separators()  # tolerate blank lines between key and block
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, self.item_sep)

        # Primitives
        if t.type in (TokenType.STRING, TokenType.NUMBER, TokenType.BOOLEAN,
                      TokenType.NULL, TokenType.DATETIME):
            tok = self.consume()
            return ScalarNode(tok.value, tok.line, tok.col)

        raise FlexConfError(f"Unexpected token {t.type}", t.line, t.col)

    def _is_map_entry(self):
        # Look ahead: IDENTIFIER/STRING/NUMBER followed by KV_SEP?
        # (Language SPEC: bare keys may start with digits, e.g. `0: value`)
        t1 = self.peek(0)
        t2 = self.peek(1)
        if t1.type in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER) and t2.type == TokenType.KVSEP:
            return True
        return False

    def _parse_key(self):
        t = self.consume()
        if t.type not in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER):
            raise FlexConfError("Expected key", t.line, t.col)
        # Bare keys are strings; digit-leading keys (e.g. `0:`) are stringified
        if t.type == TokenType.NUMBER:
            return str(t.value)
        return t.value


# --- Interpreter ---

class Interpreter:
    """Converts the AST (IR) into native Python data structures
    (Parser SPEC 5.1: Map -> dict, anonymous map -> list, primitives as-is).

    The parser builds anonymous maps directly as ListNodes — the direct
    array construction route recommended by Parser SPEC 5.2 — so no
    intermediate "string-keyed map" form exists here.
    """

    def to_native(self, node: Node):
        if isinstance(node, MapNode):
            return {key: self.to_native(child) for key, child in node.entries.items()}
        if isinstance(node, ListNode):
            return [self.to_native(child) for child in node.elements]
        if isinstance(node, ScalarNode):
            return node.value
        raise FlexConfError(f"Unknown AST node {type(node).__name__}", node.line, node.col)


# --- API ---

def parse(text: str, config: Config = None) -> Node:
    """Parse FlexConf source text into an AST (IR) without interpreting it.

    The returned tree (MapNode / ListNode / ScalarNode, with line/column
    info) is the entry point for tooling: formatters, linters, serializers.

    `config` (a Config) sets the base syntax configuration; pragma
    directives in the document apply on top of it (Parser SPEC 3.1).
    """
    lexer = Lexer(text, config)
    tokens = lexer.tokenize()
    return Parser(tokens, lexer.config).parse()


def loads(text: str, config: Config = None):
    return Interpreter().to_native(parse(text, config))


def load(fp, config: Config = None):
    return loads(fp.read(), config)


# --- Test ---

if __name__ == "__main__":
    try:
        # Test INDENT style
        indent_code = """
server:
    host: "localhost"
    port: 8080

    admin:
        enabled: true

list_example:
    1
    2
    3
"""
        print("--- INDENT style ---")
        print(loads(indent_code))

        # Test BRACE style
        bracket_code = """
{
    server: {
        host: "localhost",
        port: 8080
    },
    list_example: { 1, 2, 3 }
}
"""
        print("\n--- BRACE style ---")
        print(loads(bracket_code))

        # Test pragma-driven customization
        custom_code = """
#?> SET ITEMSEP ';'
{
    server: {
        host: "localhost";  # semicolons and # comments
        port: 8080
    }
}
"""
        print("\n--- Custom separators via pragma ---")
        print(loads(custom_code))
    except Exception:
        import traceback
        traceback.print_exc()
