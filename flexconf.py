import re
import sys
from enum import Enum, auto
from math import gcd
from typing import Any

# --- Configuration & Constants ---

class TokenType(Enum):
    # Primitives
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()
    IDENTIFIER = auto()

    # Structure
    LBRACE = auto()        # {
    RBRACE = auto()        # }
    COLON = auto()         # :
    COMMA = auto()         # ,
    NEWLINE = auto()       # \n

    # Indentation
    INDENT = auto()
    DEDENT = auto()

    EOF = auto()

class Token:
    def __init__(self, token_type: TokenType, value: Any, line: int, col: int):
        self.type = token_type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)}, line={self.line})"

class FlexConfError(Exception):
    def __init__(self, message, line, col):
        super().__init__(f"{message} at line {line}, column {col}")

# --- Lexer ---

class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.indent_stack = [0]

        # Configuration (Extensibility)
        self.config = {
            'block_start': '{',
            'block_end': '}',
            'separator': ',',
            'key_val_sep': ':',
            'comment': '#'
        }

        self._scan_pragmas()
        self.mode = self._detect_mode()

    def _scan_pragmas(self):
        # Pragma directives (#?>) are part of the extensibility roadmap
        # (Language SPEC: Extensibility) and are not implemented yet.
        # The configuration object above is already in place so a future
        # pragma processor can update it before tokenization (Parser SPEC 7).
        pass

    def _detect_mode(self):
        # Skip whitespace and comments to find first char
        p = 0
        while p < len(self.text):
            char = self.text[p]
            if char.isspace():
                p += 1
                continue
            if char == self.config['comment']:
                # Skip comment line
                while p < len(self.text) and self.text[p] != '\n':
                    p += 1
                continue

            if char == self.config['block_start']:
                return 'bracket'
            else:
                return 'indentation'
        return 'indentation' # Default empty file

    def _compute_base_indent_unit(self):
        # Base indent unit = GCD of all non-zero indentation widths
        # (Language SPEC: Indentation Mode). Blank and comment-only lines excluded.
        base = None
        for line in self.text.split('\n'):
            content = line.lstrip(' ')
            if not content.strip():
                continue # blank line
            if content.startswith(self.config['comment']):
                continue # comment-only line
            indent = len(line) - len(content)
            if indent > 0:
                base = indent if base is None else gcd(base, indent)
        return base

    def tokenize(self) -> list[Token]:
        self.tokens = []
        self.indent_stack = [0]
        self.base_indent_unit = self._compute_base_indent_unit()

        # Handle initial indentation/content for indentation mode
        if self.mode == 'indentation':
            self._handle_indentation()

        while self.pos < len(self.text):
            char = self.text[self.pos]

            # 1. Handle Whitespace / Indentation
            if char == '\n':
                self._advance()
                if self.mode == 'indentation':
                    self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line-1, self.col))
                    self._handle_indentation()
                continue

            if char.isspace():
                self._advance()
                continue

            # 2. Handle Comments
            if char == self.config['comment']:
                self._skip_comment()
                continue

            # 3. Handle Structure
            if char == '{':
                if self.mode == 'indentation':
                     raise FlexConfError("Unexpected '{' in indentation mode", self.line, self.col)
                self.tokens.append(Token(TokenType.LBRACE, '{', self.line, self.col))
                self._advance()
                continue

            if char == '}':
                if self.mode == 'indentation':
                     raise FlexConfError("Unexpected '}' in indentation mode", self.line, self.col)
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                self._advance()
                continue

            if char == ':':
                self.tokens.append(Token(TokenType.COLON, ':', self.line, self.col))
                self._advance()
                continue

            if char == ',':
                if self.mode == 'indentation':
                     raise FlexConfError("Unexpected ',' in indentation mode", self.line, self.col)
                self.tokens.append(Token(TokenType.COMMA, ',', self.line, self.col))
                self._advance()
                continue

            # 4. Handle Primitives
            token = self._parse_primitive()
            if token:
                self.tokens.append(token)
                continue

            raise FlexConfError(f"Unexpected character '{char}'", self.line, self.col)

        # EOF Handling
        if self.mode == 'indentation':
            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, None, self.line, self.col))

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return self.tokens

    def _flush_blanks(self, n):
        # A blank line emits a NEWLINE token (Parser SPEC 3.4)
        for _ in range(n):
            self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line, 1))

    def _handle_indentation(self):
        # Consumes whitespace/comments/newlines until a real line starts
        # Calculates indentation and emits INDENT/DEDENT.
        # Blank lines are buffered; when they precede a dedent, they are
        # emitted AFTER the DEDENT tokens (together with the moved line-end
        # NEWLINE), so a blank line stays visible at the level whose items
        # it separates (anonymous maps in lists, Parser SPEC 4.2).

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
                self._advance(p - self.pos + 1) # Consume spaces + newline
                pending_blanks += 1
                continue
            elif c == self.config['comment']:
                # Comment line, ignore (generates no tokens)
                self._advance(p - self.pos) # Consume spaces
                self._skip_comment()
                # After comment, we might have newline, loop again
                if self.pos < len(self.text) and self.text[self.pos] == '\n':
                    self._advance()
                    continue
                break
            else:
                # Real content found
                self._advance(p - self.pos) # Consume the spaces
                indent_len = spaces

                # Base unit was precomputed from the whole document
                if self.base_indent_unit and indent_len > 0 and indent_len % self.base_indent_unit != 0:
                    raise FlexConfError("Indentation not a multiple of base unit", self.line, self.col)

                current_level = self.indent_stack[-1]
                if indent_len > current_level:
                    self._flush_blanks(pending_blanks)
                    # Emit one INDENT per indentation level (Parser SPEC 3.4),
                    # so the parser can detect the extra level of anonymous
                    # map items inside lists.
                    base = self.base_indent_unit or indent_len
                    level = current_level + base
                    while level < indent_len:
                        self.indent_stack.append(level)
                        self.tokens.append(Token(TokenType.INDENT, None, self.line, self.col))
                        level += base
                    self.indent_stack.append(indent_len)
                    self.tokens.append(Token(TokenType.INDENT, None, self.line, self.col))
                elif indent_len < current_level:
                    # Move the preceding line-end NEWLINE past the DEDENTs so
                    # the enclosing level sees it (and any blank lines).
                    moved_newline = None
                    if self.tokens and self.tokens[-1].type == TokenType.NEWLINE:
                        moved_newline = self.tokens.pop()
                    while indent_len < current_level:
                        self.indent_stack.pop()
                        current_level = self.indent_stack[-1]
                        self.tokens.append(Token(TokenType.DEDENT, None, self.line, self.col))
                    if indent_len != current_level:
                        raise FlexConfError("Unindent does not match any outer indentation level", self.line, self.col)
                    if moved_newline is not None:
                        self.tokens.append(moved_newline)
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
        while self.pos < len(self.text) and self.text[self.pos] != '\n':
            self._advance()

    def _parse_primitive(self):
        # Shared by both modes: quoted strings are read in place; bare
        # literals run until a structural delimiter and are then classified.
        char = self.text[self.pos]

        # String
        if char in ('"', "'"):
            # Simple string parser (does not handle all escapes/multiline perfectly in this ref)
            quote = char
            end_quote = self.text.find(quote, self.pos + 1)
            if end_quote == -1:
                raise FlexConfError("Unterminated string", self.line, self.col)
            val = self.text[self.pos+1:end_quote]
            length = end_quote - self.pos + 1
            token = Token(TokenType.STRING, val, self.line, self.col)
            self._advance(length)
            return token

        # Other literals
        # Read until delimiter
        start_pos = self.pos
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c in ' \t\n\r:{},#':
                break
            self._advance()

        raw = self.text[start_pos:self.pos]
        if not raw: return None

        type_, val = self._classify_literal(raw)
        return Token(type_, val, self.line, self.col - len(raw))

    def _classify_literal(self, raw):
        if raw == 'true': return TokenType.BOOLEAN, True
        if raw == 'false': return TokenType.BOOLEAN, False
        if raw == 'null': return TokenType.NULL, None

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
    """A list of child nodes. Anonymous map items in indentation mode are
    plain MapNode elements here."""
    def __init__(self, elements: list, line: int, col: int):
        super().__init__(line, col)
        self.elements = elements  # list[Node]

    def __repr__(self):
        return f"ListNode({len(self.elements)} items, line={self.line})"

# --- Parser ---

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0) -> Token:
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return self.tokens[-1] # EOF

    def consume(self, type_: TokenType = None):
        token = self.peek()
        if type_ and token.type != type_:
            raise FlexConfError(f"Expected {type_.name}, got {token.type.name}", token.line, token.col)
        self.pos += 1
        return token

    def parse(self):
        # Determine mode from first token or structure
        # But Lexer already handled mode-specific tokenization.
        # We just need to parse the stream.

        # Unified parsing:
        # If stream starts with LBRACE, it's a bracket block.
        # If stream starts with INDENT or primitives, it's an indentation block (implicit root).

        # However, the root of an indentation file is a bit special because it doesn't start with INDENT.
        # It's a list of items separated by NEWLINE.
        # We can treat the whole file as a block if we imagine implicit braces around it.

        # For now, let's keep the entry point simple but unify the block parsing logic.

        first = self.peek()
        if first.type == TokenType.LBRACE:
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, TokenType.COMMA)
        else:
            # Indentation root is like a block but without surrounding braces
            return self._parse_items(TokenType.EOF, TokenType.NEWLINE)

    def _parse_block(self, start_token, end_token, separator_token):
        start = self.consume(start_token)

        # Two consecutive INDENTs: the block skipped the list level, so it is
        # a List whose anonymous Map items sit one level deeper (SPEC 4.2).
        if start_token == TokenType.INDENT and self.peek().type == TokenType.INDENT:
            self.consume()
            return self._parse_list_block(start.line, start.col)

        # Check if empty block
        if self.peek().type == end_token:
            self.consume()
            return MapNode({}, start.line, start.col) # Default to empty map

        result = self._parse_items(end_token, separator_token)
        self.consume(end_token)
        return result

    def _parse_list_block(self, line, col):
        # List whose items are anonymous maps (at the deeper level, separated
        # by exactly one blank line) and/or scalars (at the list level).
        elements = []

        # Anonymous map items at the deeper level
        while True:
            self._skip_separators()
            if self.peek().type in (TokenType.DEDENT, TokenType.EOF):
                break
            elements.append(self._parse_anonymous_map())

        self.consume(TokenType.DEDENT) # map level -> list level

        # Scalar items at the list level
        while self.peek().type not in (TokenType.DEDENT, TokenType.EOF):
            if self.peek().type == TokenType.NEWLINE:
                self.consume()
                continue
            elements.append(self._parse_value())

        self.consume(TokenType.DEDENT) # list level -> enclosing level
        return ListNode(elements, line, col)

    def _parse_anonymous_map(self):
        # Anonymous map inside a list: key-value pairs at the same level,
        # ended by a blank line (two consecutive NEWLINEs) or by DEDENT.
        start = self.peek()
        res = {}
        while True:
            t = self.peek()
            if t.type in (TokenType.DEDENT, TokenType.EOF):
                break
            if t.type == TokenType.NEWLINE:
                if self.peek(1).type in (TokenType.NEWLINE, TokenType.DEDENT, TokenType.EOF):
                    break # blank line ends this map item
                self.consume()
                continue
            key_token = self.peek()
            key = self._parse_key()
            self.consume(TokenType.COLON)
            val = self._parse_value()
            if key in res:
                raise FlexConfError(f"Duplicate key '{key}'", key_token.line, key_token.col)
            res[key] = val
        return MapNode(res, start.line, start.col)

    def _skip_separators(self):
        while self.peek().type == TokenType.NEWLINE:
            self.consume()

    def _parse_items(self, end_token, separator_token):
        # Generic item parser for both Map and List content
        # Sniff first item to decide if it's a Map or List

        self._skip_separators() # tolerate leading blank lines
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
            self.consume(TokenType.COLON)
            val = self._parse_value()
            if key in res:
                raise FlexConfError(f"Duplicate key '{key}'", key_token.line, key_token.col)
            res[key] = val

            if self.peek().type == separator_token:
                self.consume()
            elif self.peek().type != end_token:
                 # In bracket mode, comma is usually required, but let's be lenient or strict based on spec
                 # Spec says "Commas separate items".
                 # If we are at end_token, loop terminates. If not, and no comma, it's an error?
                 # For indentation mode, separator is NEWLINE.
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

        # Bracket Block
        if t.type == TokenType.LBRACE:
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, TokenType.COMMA)

        # Indentation Block
        if t.type == TokenType.NEWLINE:
            self.consume()
            self._skip_separators() # tolerate blank lines between key and block
            return self._parse_block(TokenType.INDENT, TokenType.DEDENT, TokenType.NEWLINE)

        if t.type == TokenType.INDENT:
             return self._parse_block(TokenType.INDENT, TokenType.DEDENT, TokenType.NEWLINE)

        # Primitives
        if t.type in (TokenType.STRING, TokenType.NUMBER, TokenType.BOOLEAN, TokenType.NULL):
            tok = self.consume()
            return ScalarNode(tok.value, tok.line, tok.col)

        raise FlexConfError(f"Unexpected token {t.type}", t.line, t.col)

    def _is_map_entry(self):
        # Look ahead: IDENTIFIER/STRING/NUMBER followed by COLON?
        # (Language SPEC: bare keys may start with digits, e.g. `0: value`)
        t1 = self.peek(0)
        t2 = self.peek(1)
        if t1.type in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.NUMBER) and t2.type == TokenType.COLON:
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
    (Parser SPEC 5.1: Map -> dict, List -> list, primitives as-is).

    The parser builds lists directly as ListNodes, so the "integer-keyed
    map to array" conversion of Parser SPEC 5.2 has no intermediate form
    to apply here (the SPEC allows direct list construction).
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

def parse(text: str) -> Node:
    """Parse FlexConf source text into an AST (IR) without interpreting it.

    The returned tree (MapNode / ListNode / ScalarNode, with line/column
    info) is the entry point for tooling: formatters, linters, serializers.
    """
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    return Parser(tokens).parse()

def loads(text: str):
    return Interpreter().to_native(parse(text))

def load(fp):
    return loads(fp.read())

# --- Test ---

if __name__ == "__main__":
    try:
        # Test Indentation Mode
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
        print("--- Indentation Mode ---")
        print(loads(indent_code))

        # Test Bracket Mode
        bracket_code = """
{
    server: {
        host: "localhost",
        port: 8080
    },
    list_example: { 1, 2, 3 }
}
"""
        print("\n--- Bracket Mode ---")
        print(loads(bracket_code))
    except Exception as e:
        import traceback
        traceback.print_exc()
