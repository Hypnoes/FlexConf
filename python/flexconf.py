import io
from pathlib import Path
from enum import Enum, auto
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
        # Simple scan for #?> at start of file
        # In a full implementation, this would parse and update self.config
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

    def tokenize(self) -> list[Token]:
        self.tokens = []
        self.indent_stack = [0]
        self.base_indent_unit = None

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

    def _handle_indentation(self):
        # Consumes whitespace/comments/newlines until a real line starts
        # Calculates indentation and emits INDENT/DEDENT

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
                # Empty line with spaces, ignore
                self._advance(p - self.pos + 1) # Consume spaces + newline
                continue
            elif c == self.config['comment']:
                # Comment line, ignore
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

                # Determine Base Unit
                if self.base_indent_unit is None and indent_len > 0:
                    self.base_indent_unit = indent_len

                if self.base_indent_unit and indent_len > 0 and indent_len % self.base_indent_unit != 0:
                    raise FlexConfError("Indentation not a multiple of base unit", self.line, self.col)

                current_level = self.indent_stack[-1]
                if indent_len > current_level:
                    self.indent_stack.append(indent_len)
                    self.tokens.append(Token(TokenType.INDENT, None, self.line, self.col))
                elif indent_len < current_level:
                    while indent_len < current_level:
                        self.indent_stack.pop()
                        current_level = self.indent_stack[-1]
                        self.tokens.append(Token(TokenType.DEDENT, None, self.line, self.col))
                    if indent_len != current_level:
                        raise FlexConfError("Unindent does not match any outer indentation level", self.line, self.col)

                return

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
        # Used by bracket mode tokenizer
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

    def _match_string(self, text):
        # Returns (length, value)
        quote = text[0]
        # Handle triple quote
        if text.startswith(quote * 3):
            quote = quote * 3

        # Find end
        end = text.find(quote, len(quote))
        if end == -1: return None
        return (end + len(quote), text[len(quote):end])

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

# --- Parser ---

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0) -> Token:
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return self.tokens[-1] # EOF

    def consume(self, type_: TokenType | None = None):
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
        self.consume(start_token)

        # Check if empty block
        if self.peek().type == end_token:
            self.consume()
            return {} # Default to empty map

        result = self._parse_items(end_token, separator_token)
        self.consume(end_token)
        return result

    def _parse_items(self, end_token, separator_token):
        # Generic item parser for both Map and List content
        # Sniff first item to decide if it's a Map or List

        is_map = self._is_map_entry()

        if is_map:
            return self._finish_map(end_token, separator_token)
        else:
            return self._finish_list(end_token, separator_token)

    def _finish_map(self, end_token, separator_token):
        res = {}
        while self.peek().type != end_token and self.peek().type != TokenType.EOF:
            if self.peek().type == separator_token:
                self.consume()
                continue

            key = self._parse_key()
            self.consume(TokenType.COLON)
            val = self._parse_value()
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
        return res

    def _finish_list(self, end_token, separator_token):
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
        return res

    def _parse_value(self):
        t = self.peek()

        # Bracket Block
        if t.type == TokenType.LBRACE:
            return self._parse_block(TokenType.LBRACE, TokenType.RBRACE, TokenType.COMMA)

        # Indentation Block
        if t.type == TokenType.NEWLINE:
            self.consume()
            return self._parse_block(TokenType.INDENT, TokenType.DEDENT, TokenType.NEWLINE)

        if t.type == TokenType.INDENT:
             return self._parse_block(TokenType.INDENT, TokenType.DEDENT, TokenType.NEWLINE)

        # Primitives
        if t.type in (TokenType.STRING, TokenType.NUMBER, TokenType.BOOLEAN, TokenType.NULL):
            return self.consume().value

        raise FlexConfError(f"Unexpected token {t.type}", t.line, t.col)

    def _is_map_entry(self):
        # Look ahead: IDENTIFIER/STRING followed by COLON?
        t1 = self.peek(0)
        t2 = self.peek(1)
        if t1.type in (TokenType.IDENTIFIER, TokenType.STRING) and t2.type == TokenType.COLON:
            return True
        return False

    def _parse_key(self):
        t = self.consume()
        if t.type not in (TokenType.IDENTIFIER, TokenType.STRING):
            raise FlexConfError("Expected key", t.line, t.col)
        return t.value

# --- API ---

def loads(text: str):
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()

def load(fp: io.TextIOBase):
    return loads(fp.read())

# --- Test ---

if __name__ == "__main__":
    try:
        # Test Indentation Mode
        indent_code = Path("examples/conf_1.fc").read_text()
        print("--- Indentation Mode ---")
        print(loads(indent_code))

        print()
        # Test Bracket Mode
        bracket_code = Path("examples/conf_2.fc").read_text()
        print("--- Bracket Mode ---")
        print(loads(bracket_code))
    except Exception as e:
        import traceback
        traceback.print_exc()
