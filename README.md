# FlexConf

FlexConf is a new format of configuration language—formally defined by the `flex-config` format—that offers interchangeable **indentation** and **bracket** syntaxes without sacrificing readability or machine friendliness. This repository collects the normative specifications, a pedagogical Python reference parser, and sample configuration files to help you learn and adopt the format quickly.

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
| `python/` | Minimal Python lexer/parser (`flexconf.py`) with CLI entry point for experimentation. |
| `examples/` | Sample `.fc` files demonstrating indentation (`conf_1.fc`) and bracket (`conf_2.fc`) modes. |

---

## Language Summary

FlexConf documents are UTF-8 encoded and must commit to a single syntax mode per file:

- **Indentation Mode** relies on significant whitespace, much like YAML, with strict indentation-unit validation.
- **Bracket Mode** mirrors JSON-like braces, commas, and explicit list/map delimiters.

Across both syntaxes, FlexConf supports:

- Primitive types: strings (basic, literal, multi-line), numbers (dec/hex/oct/bin, floats, special floats), booleans, null.
- Structured types: maps (explicit keys) and lists (implicit numeric keys) that can nest arbitrarily.
- Comments prefixed by `#`.
- Optional pragma directives (`#?> ...`) that enable per-file customization of delimiters and separators.

See `FlexConf Language SPEC.md` for the full narrative, including conversion rules, validity constraints, and extensibility roadmap.

---

## Formal Grammar (ABNF)

`FlexConf ABNF Grammar SPEC.md` expresses the complete grammar in ABNF, covering:

- Core character classes and tokens.
- Document start symbols for both syntax modes.
- String, numeric, and structural productions.
- Validation notes for constraints that lie outside pure ABNF (e.g., indentation consistency, duplicate keys).

Use this document when implementing parsers with parser generators, verifying compliance, or building syntax highlighters.

---

## Parser Requirements

`FlexConf Parser SPEC.md` details:

1. **Lexer Responsibilities**
   - UTF-8 enforcement, pragma preprocessing, mode detection.
   - Token stream covering literals, structure tokens, and indentation markers.
2. **Parser Architecture**
   - Unified container model where lists are keyed maps internally.
   - Strategies for disambiguating map vs. list blocks in each syntax mode.
3. **Interpreter & Error Handling**
   - Mapping tokens to host-language types.
   - Descriptive diagnostics with line/column context.
4. **Extensibility Hooks**
   - Configuration object for runtime-adjustable delimiters.
   - Dynamic tokenization guided by pragma directives.

Consult this spec before porting the parser to new languages or extending the reference implementation.

---

## Python Reference Parser

The `python/flexconf.py` module illustrates the full pipeline and exposes importable entry points you can reuse in other projects:

- `TokenType` and `Token` define the primitive and structural vocabulary consumed throughout the parser.
- `Lexer` implements indentation stacks, comment skipping, and bracket-mode guards exactly as described in the specs.
- `Parser` turns the token stream into Python dict/list structures via `_parse_block`, `_finish_map`, and `_finish_list`.
- `loads` and `load` mirror Python’s `json` API and provide the recommended interface for libraries.
- The `if __name__ == "__main__":` harness parses `examples/conf_1.fc` (indentation mode) and `examples/conf_2.fc` (bracket mode) for quick smoke tests.

Run the script directly to see the demonstration output:

```FlexConf/python/flexconf.py#L454-468
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
```

Or import it programmatically:

```FlexConf/python/flexconf.py#L443-450
def loads(text: str):
    lexer = Lexer(text)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()

def load(fp: io.TextIOBase):
    return loads(fp.read())
```

Use this implementation as a learning aid or lightweight tooling foundation; it intentionally prioritizes clarity over micro-optimizations and is provided strictly as a demonstration reference, not production-ready code.

---

## Example Configurations

The `examples/` directory contains two canonical files:

1. `conf_1.fc` – indentation-mode map plus list demonstrating nested structures and list semantics driven by blank-line separation:
```FlexConf/examples/conf_1.fc#L1-11
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

2. `conf_2.fc` – bracket-mode equivalent showing explicit braces and commas for the same data:
```FlexConf/examples/conf_2.fc#L1-7
{
    server: {
        host: "localhost",
        port: 8080
    },
    list_example: { 1, 2, 3 }
}
```

Diffing these files highlights the one-to-one correspondence between syntaxes, making them ideal fixtures for parser unit tests or documentation snippets.

---

## Getting Started

1. **Read the specs** to understand the language guarantees.
2. **Run the Python parser** against the provided examples or your own `.fc` files.
3. **Experiment with pragma directives** (future roadmap) by extending the lexer configuration.
4. **Build your own parser** using the ABNF and parser spec as guides.

---

## Roadmap Ideas

### Language Roadmap
- Preprocessing hooks for custom delimiter selection, indentation/brace remapping, and enabling `//` comments when operating in brace mode.
- First-class `datetime` data type with ISO-8601 parsing, timezone awareness, and canonical serialization.

### Ecosystem
- Enhanced pragma processing and validation tooling.
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