# FlexConf

FlexConf is a new format of configuration language—formally defined by the `flex-config` format—built on a **single unified structural model with a configurable surface syntax**. Four syntax parameters (`KeyValueSeparator`, `ItemSeparator`, `LeftBrace`, `RightBrace`) define how a document is written, and two canonical presets—the **BRACE** style and the **INDENT** style—cover the familiar JSON-like and YAML-like surfaces without sacrificing readability or machine friendliness. This repository collects the normative specifications, a pedagogical Python reference parser, and sample configuration files to help you learn and adopt the format quickly.

Although this design has basically taken shape, there are still some details under consideration and it will continue to evolve until it is finally finalized.

---

## Project Highlights

- **Language Spec** – authoritative description of FlexConf semantics, types, and syntax rules.
- **ABNF Grammar** – formal definition suitable for parser generator tooling.
- **Parser Spec** – implementation guidance covering lexing, parsing, error handling, and extensibility hooks.
- **Python Reference Parser** – concise example that demonstrates the end-to-end pipeline from text to native data structures.
- **Example Configs** – paired indentation and bracket documents that showcase identical data expressed with each syntax.

---

## Repository Layout

| Path | Description |
| --- | --- |
| `FlexConf Language SPEC.md` | Human-readable narrative specification for language users. |
| `FlexConf ABNF Grammar SPEC.md` | Machine-oriented ABNF grammar capturing the full syntax. |
| `FlexConf Parser SPEC.md` | Architectural requirements for compliant parser implementations. |
| `flexconf.py` | Python reference implementation: lexer, parser, AST, and interpreter, with a demo entry point. |
| `test_flexconf.py` | Self-contained test script (71 checks) covering both canonical styles, pragma-driven customization, date/time literals, reserved meta-syntax, and the AST layer. |
| `examples/` | Sample `.fc` files demonstrating the INDENT (`conf_1.fc`) and BRACE (`conf_2.fc`) styles. |

---

## Language Summary

FlexConf documents are UTF-8 encoded. Every document is a hierarchy of **blocks** governed by four configurable syntax parameters; the two canonical presets are:

- **BRACE style** (default): `{`/`}` blocks, `,` item separator, `:` key-value separator, `#` comments. All whitespace is insignificant, so documents may be reflowed freely.
- **INDENT style**: the same model with `LeftBrace = <INDENT>`, `RightBrace = <DEDENT>`, `ItemSeparator = <NEWLINE>` — significant indentation and newlines, much like YAML, with strict indentation-unit validation. Enable it explicitly with `#?> SET STYLE INDENT`; documents without pragmas are auto-detected (a leading `{` selects BRACE, anything else INDENT).

Across all styles, FlexConf supports:

- Primitive types: strings (basic, literal, multi-line), numbers (dec/hex/oct/bin, floats, special floats), booleans, null, and date/time literals — `@`-sigiled RFC 3339 profiles such as `@1979-05-27T07:32:00Z`, `@1979-05-27 07:32:00`, `@1979-05-27`, or `@07:32:00`, mapping to native date/time types.
- Structured types: maps (explicit keys) and anonymous maps — traditionally called lists — whose implicit keys are the strings `"0"`, `"1"`, ... assigned in order of appearance. Both nest arbitrarily.
- Line comments introduced by `#`.
- Pragma directives (`#?> SET ...`) that customize any syntax parameter per file, e.g. `#?> SET ItemSeparator ';'` or `#?> SET STYLE INDENT`.

See `FlexConf Language SPEC.md` for the full narrative, including the whitespace significance rules, conversion rules, and validity constraints.

---

## Reserved Words and Symbols

FlexConf reserves a small set of words and symbols on top of the four configurable syntax parameters. Some are fixed meta-syntax that no configuration can change; others are reserved only in a particular position. Misusing one is a common source of `SyntaxError`s, so the tables below pair each entry with the context in which it is safe.

### Fixed meta-syntax

| Symbol | Role | How to use it as data |
| --- | --- | --- |
| `#` | Runs a comment to the end of the line. | Put the `#` inside a quoted string: `"a#b"`. |
| `#?>` | Starts a pragma directive; pragmas form a contiguous block at the head of the file. | Write `# ?>` if a comment is intended; a `#?>` outside the block is an error, not a comment. |
| `@` | Starts a date/time literal such as `@2026-10-09`. | Quote anything else containing `@`: `"user@example.com"`. |
| `!` | Reserved for future use; it currently has no meaning. | Quote it: `"a!b"` — a bare `!` is an error. |

A separator value must not contain `@` or `!`, and the comment marker `#` must not equal a separator or share a prefix with one. `#?>` is recognized only as part of the head pragma block, so it is not a separator concern.

### Context-reserved words

| Words | Reserved where | Free where |
| --- | --- | --- |
| `SET`, `STYLE`, `BRACE`, `INDENT`, `KeyValueSeparator`, `ItemSeparator`, `LeftBrace`, `RightBrace`, `<INDENT>`, `<DEDENT>`, `<NEWLINE>` | On a line beginning with `#?>` — these are the only accepted pragma vocabulary, and matching is case-sensitive. | Anywhere else they are ordinary text; `SET: 1` is a valid key. |
| `true`, `false`, `null` | Everywhere: they are lexed as literal types, so they cannot be bare keys. | Quote them to use them as keys. |
| `inf`, `+inf`, `-inf`, `nan` | Value position, where they denote special floats. | As bare keys they are allowed too: `inf: 1` makes the string key `"inf"`. |

The string and key delimiters are fixed as well: `"` and `'` open strings, `` ` `` opens a quoted key, and `\` starts an escape inside a basic double-quoted string. They are never configurable, and a separator value may not contain any of them. By contrast, the structural characters `:`, `,`, `{`, and `}` are reserved only while the effective configuration binds them — change the parameter and the character becomes ordinary.

### Watch Out

- **`#` always starts a comment** outside a string. `key: value  # note` is fine, but `key: a#b` is not the string `"a#b"` — quote it.
- **Every `@` outside a string must begin a valid date/time.** `user@example.com` is a `SyntaxError`; `"user@example.com"` is a string. A malformed literal such as `@foo` or a calendar-invalid one such as `@2026-02-30` also fails.
- **`!` is reserved and currently meaningless.** A bare `!` outside a string is a `SyntaxError`; quote it (`"a!b"`) to use it as data, and keep it out of custom separator values.
- **`#?>` is reserved, and pragmas are one contiguous block.** They must be a contiguous run of `#?>` lines at the very start of the file, with only whitespace, blank lines, or comments before them. A comment or blank line between two directives ends the block, and any later `#?>` line (outside a quoted string) is a `SyntaxError` — never silently treated as a comment.
- **Reserved symbols end a bare word.** `a'b`, `a"b`, `` a`b ``, `a#b`, `a@b`, and `a!b` are all invalid: the symbol terminates the word and then takes its own role (a quote opens a string, `#` starts a comment, `@` must begin a date/time, `!` is an error). Quote the text (`"a@b"`) to keep it as data.
- **A bare value is a closed set.** Outside strings it can only be `true`/`false`, `null`, a number (including `inf`/`nan`), or a `@` date/time; `host: localhost` fails — write `host: "localhost"`.
- **`true`/`false`/`null` cannot be bare keys.** `true: 1` fails because the word is lexed as a boolean; quote it (`"true": 1`, or a backtick-quoted key in spec terms).
- **A numeric-looking bare key is a string key.** The spec treats the key as its literal spelling; the reference parser instead normalizes through the numeric value, so `+99:` yields `"99"`, `1_000:` yields `"1000"`, `1.50:` yields `"1.5"`, and `5e2:` yields `"500.0"`. Quote the key when the exact spelling matters.
- **Custom separators are constrained.** A separator must be non-empty, contain no whitespace and no `"`, `'`, `` ` ``, or `@`, must not be a prefix of another separator, and must not collide with `#`. So `#?> SET ItemSeparator '@'` is invalid, and `#?> SET ItemSeparator ':,'` is invalid because `:,` has the default `:` as a prefix.
- **In the INDENT style, `{` and `}` are not data.** A literal brace outside a string is a `SyntaxError`; quote it (`"{a}"`).

### Reference Parser Note

The bundled `flexconf.py` is a demonstration, not a complete implementation, and it diverges from the specs in a few places that involve reserved words:

- It keeps the backticks of a quoted key in the key string, so prefer a double-quoted key (`"true": 1`) in its examples; the normative quoted-key form is the backtick.
- It does not implement hex/octal/binary literals (`0x...`, `0o...`, `0b...`) or triple-quoted strings, and it does not process `\` escapes inside basic strings.

Use the specifications as the normative reference and treat the reference parser as a learning aid.

---

## Formal Grammar (ABNF)

`FlexConf ABNF Grammar SPEC.md` expresses the complete grammar in ABNF, covering:

- Core character classes and tokens.
- The parameterized block grammar with its default (BRACE style) instantiation and the INDENT-style virtual token bindings.
- String, numeric, and structural productions.
- Validation notes for constraints that lie outside pure ABNF (e.g., indentation consistency, duplicate keys, configuration validity).

Use this document when implementing parsers with parser generators, verifying compliance, or building syntax highlighters.

---

## Parser Requirements

`FlexConf Parser SPEC.md` details:

1. **Lexer Responsibilities**
   - UTF-8 enforcement, pragma preprocessing, style resolution and surface detection.
   - A single token vocabulary covering literals, separators, and (literal or virtual) braces.
2. **Parser Architecture**
   - Unified container model: a block is a map (explicit keys) or an anonymous map (implicit keys `"0"`, `"1"`, ...), decided by item form.
   - One surface-agnostic block-parsing strategy driven by the effective configuration.
3. **Interpreter & Error Handling**
   - Mapping tokens to host-language types; anonymous maps become native arrays directly, with no prescribed intermediate representation.
   - Descriptive diagnostics with line/column context.
4. **Configuration & Pragmas**
   - A validated configuration object holding the four syntax parameters and the style presets.
   - Dynamic tokenization guided by pragma directives (`SET STYLE`, single-parameter `SET`).

Consult this spec before porting the parser to new languages or extending the reference implementation.

---

## Python Reference Parser

The `flexconf.py` module illustrates the full pipeline and exposes importable entry points you can reuse in other projects:

- `Config` holds the four syntax parameters with upfront validation; `Config.style_brace()` / `Config.style_indent()` build the named presets (both accept field overrides).
- `TokenType` and `Token` define the unified vocabulary consumed throughout the parser; `INDENT`/`DEDENT`/`NEWLINE` tokens are the virtual `<INDENT>`/`<DEDENT>`/`<NEWLINE>` parameter bindings.
- `Lexer` scans `#?>` pragma directives, resolves the style and surface, then tokenizes with the effective configuration (including multi-character literal separators).
- `Parser` turns the token stream into an AST of `MapNode`, `ListNode`, and `ScalarNode` objects (each carrying line/column info) via `_parse_block`, `_finish_map`, and `_finish_list`. `ListNode` realizes an anonymous map directly as an ordered sequence — its implicit key is the element index.
- `Interpreter` walks the AST and produces native Python dict/list structures.
- `parse` returns the AST for tooling; `loads` and `load` mirror Python’s `json` API and provide the recommended interface for libraries. All three accept an optional `Config`.
- The `if __name__ == "__main__":` harness parses built-in indentation-mode and bracket-mode samples for a quick smoke test.

Run the script directly to see the demonstration output:

```bash
python flexconf.py
```

Or import it programmatically:

```python
import flexconf

data = flexconf.loads(text)  # str -> native Python objects
tree = flexconf.parse(text)  # str -> AST (MapNode / ListNode / ScalarNode)

# Custom surface syntax, no pragmas required:
cfg = flexconf.Config.style_indent(key_value_separator='=')
data = flexconf.loads(text, config=cfg)
```

Use this implementation as a learning aid or lightweight tooling foundation; it intentionally prioritizes clarity over micro-optimizations and is provided strictly as a demonstration reference, not production-ready code.

---

## Example Configurations

The `examples/` directory contains two canonical files:

1. `conf_1.fc` – INDENT-style map plus anonymous map demonstrating nested structures and blank-line separation of anonymous map items:
```
server:
    host: "localhost"
    port: 8080

    admin:
        enabled: true

list_example:
    1
    2
    3
```

2. `conf_2.fc` – BRACE-style equivalent showing explicit braces and commas for the same data:
```
{
    server: {
        host: "localhost",
        port: 8080
    },
    list_example: { 1, 2, 3 }
}
```

Diffing these files highlights the one-to-one correspondence between styles, making them ideal fixtures for parser unit tests or documentation snippets.

---

## Getting Started

1. **Read the specs** to understand the language guarantees.
2. **Run the Python demo** (`python flexconf.py`) or parse your own `.fc` files with `flexconf.loads(...)`.
3. **Run the test suite** (`python test_flexconf.py`) to see the supported behaviors exercised end to end.
4. **Experiment with pragma directives** — `#?> SET STYLE INDENT`, `#?> SET ItemSeparator ';'`, `#?> SET LeftBrace '['`, and friends — or pass a `flexconf.Config` directly.
5. **Build your own parser** using the ABNF and parser spec as guides.

---

## Roadmap Ideas

### Language Roadmap
- Serializers (`dumps`/`dump`) with style-aware pretty printing for round-tripping between styles.

### Ecosystem
- Validation tooling and richer pragma diagnostics.
- Additional reference implementations (Rust, Go, TypeScript).
- VS Code syntax highlighting and LSP server.
- Conversion utilities to/from JSON, YAML, and TOML.

If you are interested in any of these directions, open an issue or share a proposal.

---

## Contributing

Contributions are welcome! Suggested steps:

1. Fork the repository.
2. Discuss major changes in an issue before implementation.
3. Add tests and documentation updates alongside code changes.
4. Submit a pull request referencing the relevant spec sections.

---

## License

- Specifications: Creative Commons Attribution-ShareAlike 4.0 (see individual spec files).
- Source code and examples: MIT License (see `LICENSE`).

By contributing, you agree that your submissions will be licensed under the same terms.

---