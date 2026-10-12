# FlexConf Parser Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 12, 2026*

## 1. Introduction

This document specifies the requirements and architectural design for a compliant FlexConf parser and interpreter. It details the process of converting FlexConf source text into a data structure and vice versa, ensuring consistent behavior across different implementations.

FlexConf has a single unified structural model whose surface syntax is governed by four **structural tokens** (`LBRACE`, `RBRACE`, `KVSEP`, `ITEMSEP`), each realized either by a literal string or by a line-structure event, plus two canonical style presets (BRACE and INDENT). Comments are introduced by `#`. This specification describes a single parsing pipeline parameterized by the effective surface; there are no separate "indentation parser" and "bracket parser".

## 2. Architecture Overview

A FlexConf implementation typically consists of three main components:

1. **Lexer (Tokenizer)**: Converts the raw character stream into a sequence of tokens, guided by the effective surface.
2. **Parser**: Consumes tokens to build an Abstract Syntax Tree (AST) or intermediate representation, enforcing grammatical rules.
3. **Interpreter/Loader**: Converts the AST into native data structures (e.g., HashMaps, Arrays, Objects) for the host language.

## 3. Lexical Analysis

### 3.1. Input Processing

- The input must be a UTF-8 encoded stream.
- **Pragma Scanning**: Before standard tokenization, the lexer must scan the beginning of the file for pragma directives (`#?>`). The pragma prefix is fixed meta-syntax, recognized before the surface takes effect. The directives form a single **contiguous block** at the very start of the document, preceded only by whitespace, blank lines, and `#` comments; the block ends at the first line that is not a pragma line. Pragmas are applied in order of appearance — `SET STYLE <name>` binds the four tokens atomically, subsequent single-token `SET` directives rebind individual tokens — and the resulting surface is validated (§ 7) before any further processing. Unknown token names, unknown style names, and illegal values are `SyntaxError`s. Outside a string value, a `#?>` line outside the block is a `SyntaxError`, not a comment, so a misplaced directive is never silently ignored.

### 3.2. Surface Selection

The lexer must resolve the effective surface before processing the first data token.

- **Algorithm**: After pragma scanning, skip all leading whitespace and `#` comments.
  - If the first token at that position is `LBRACE` — its literal realizer wins the match there (§ 3.5) — the surface is **explicit**.
  - Otherwise the surface is **indentation**, which requires `LBRACE = <INDENT>` (and hence `RBRACE = <DEDENT>`). If the effective surface does not satisfy this, raise an `InvalidSurfaceError`.
  - A document with no pragma block declares no surface; the lexer may infer one under § 3.2.1.
- **Constraint**: Once selected, the surface is immutable for the document.

#### 3.2.1. Inferred Surfaces

- **Candidates**: inference must consider, for every token, at least the two predefined styles and every literal realizer formed by a maximal punctuation run of the document.
- **Acceptance**: an inferred surface is usable only if every surface consistent with the text yields the same data. When two consistent surfaces yield different data, the document must be rejected with an error that names the token and the competing assignments — for example, "`,` is undetermined: `ITEMSEP = ','` reads `[1,2]`, `KVSEP = ','` reads `{"1":2}`".
- **Diagnosis**: when no surface is consistent with the text, the error must be reported in the terms of the surface that consumes the longest prefix of the document.

Inference is a convenience, not part of the language definition: a document intended to be portable must carry a pragma block.

### 3.3. Token Generation

The lexer generates a stream of tokens drawn from a single vocabulary (the names below are advisory, not mandated):

- Literals: `IDENTIFIER` (bare keys), `STRING`, `NUMBER`, `BOOLEAN`, `NULL`, `DATETIME`
- `KV_SEP` — realizes `KVSEP`
- `ITEM_SEP` — realizes `ITEMSEP`
- `LBRACE`, `RBRACE` — realize `LBRACE` and `RBRACE`
- `EOF`

Each structural token is realized by either a literal string or an event (Language Specification, § Structural Tokens and Realizers). The parser consumes the four token kinds and never inspects which realizer produced them.

Comments produce no tokens. A comment runs from `#` to the end of the line.

**Date/time literals**: the sigil `@` is fixed meta-syntax (like the `#?>` pragma prefix) and never changes with the effective surface. The lexer must scan `@` and the entire date/time body that follows it as one atomic `DATETIME` token — the `:` characters inside the body never interact with `KVSEP`, and the space form of the date-time separator (RFC 3339 §5.6) is part of the atom, not a token boundary. The body must match the grammar in the ABNF specification and be followed by a delimiter or the end of input; outside strings, an `@` that does not introduce a well-formed date/time literal is a `SyntaxError`, as is a literal that fails calendar validation (e.g. `@2026-02-30`).

**Whitespace skipping**: whitespace not bound to a syntactic role is skipped between tokens. In the BRACE style this covers all spaces, tabs, and newlines. When `ITEMSEP = <NEWLINE>`, line endings produce `ITEM_SEP` tokens and are not skipped; a blank line therefore produces two consecutive `ITEM_SEP` tokens. When `LBRACE = <INDENT>`, line-leading spaces feed event token generation (§ 3.4) and are not skipped.

### 3.4. Event Token Generation (Indentation Surface)

When the indentation surface is active, the lexer realizes `LBRACE` / `RBRACE` / `ITEM_SEP` from line structure (Language Specification, § Event realizers):

- The lexer maintains a **Stack of Indentation Levels**, initialized with `[0]`.
- **Base Unit Detection**: Before tokenization, the lexer scans the document and computes the `Base Indent Unit` as the greatest common divisor of all non-zero indentation levels (blank and comment-only lines excluded). Every indentation width must be a multiple of this unit.
- **`LBRACE` emission**: When the indentation level increases, one `LBRACE` token is emitted *per level* (pushing each level onto the stack), so the parser can detect the extra level of anonymous map items (§ 4.2).
- **`RBRACE` emission**: When the indentation level decreases, one `RBRACE` per level is emitted (popping the stack).
  - *Error*: If the new level does not match a level on the stack, raise an `IndentationError`.
- **`ITEM_SEP` emission**: Each line ending produces one `ITEM_SEP`. Comment-only lines generate no tokens. Blank lines generate `ITEM_SEP` tokens (a blank line therefore yields a pair of consecutive `ITEM_SEP`s, which ends an anonymous map item, § 4.2); a blank line that precedes a dedent is emitted at the level whose items it separates.

### 3.5. Reserved Lexemes

The lexer must resolve the following before it consults the effective surface, so that no literal realizer can shadow them:

- **Fixed meta-syntax** — `#` (comment to the end of the line), `#?>` (pragma prefix, part of the contiguous head block, § 3.1), `@` (date/time sigil, § 3.3), and `!` (reserved for future use, no production). None of them may appear in a literal realizer; every `@` outside a string must open a `DATETIME` token and every other `@` is a `SyntaxError`, and a bare `!` outside a string is likewise a `SyntaxError`. Both `@` and `!` terminate a bare lexical run, so they are never absorbed into an identifier.
- **Keyword literals** — `true`, `false`, `null` (case-sensitive, lower case) and the special floats `inf`, `nan`, optionally signed. Keyword recognition precedes identifier classification, so a bare `true`, `false`, or `null` is never emitted as `IDENTIFIER`; a key written this way must be quoted in the source (Language Specification, § Reserved Words and Symbols).
- **Pragma vocabulary** — `SET`, `STYLE`, `BRACE`, `INDENT`, the four token names (`KVSEP`, `ITEMSEP`, `LBRACE`, `RBRACE`), and the event spellings `<INDENT>` / `<DEDENT>` / `<NEWLINE>`. These are reserved only within a `#?>` directive; outside the pragma section they are ordinary identifiers.
- **String and key delimiters** — `"`, `'`, and `` ` `` open strings and quoted keys, and `\` introduces an escape inside a basic string. These are never configurable.
- **Lexical boundaries** — `'`, `"`, `` ` ``, `#`, `@`, and `!` are active at *both* ends of a token: each opens its own token and each terminates a bare lexical run. The bare-run scan must stop at the first of these characters and must never absorb one into an identifier or number (`a@b` is not the identifier `a@b`; `a'b` is not the identifier `a'b`). Together with keyword recognition this restricts a bare value to booleans, `null`, numbers (including the special floats `inf` / `+inf` / `-inf` / `nan`), and `DATETIME`; every other bare word is a `SyntaxError` in value position.

- **Matching order** — at each position the candidates are every matching terminal and the bare lexical run that begins there; the longest candidate wins, and on a tie a terminal wins over the bare run. A literal realizer is therefore never matched inside a bare run, and a realizer whose characters also occur inside bare runs still matches wherever a token boundary allows it.

Resolving `#`, `@`, and `!` before the parameterized terminals is what makes the fixed meta-syntax independent of the surface; a surface that binds any of them as a literal realizer must be rejected (§ 7).

## 4. Parsing Strategy

### 4.1. Unified Container Model

Per the language design, FlexConf treats Maps and Lists as variations of a generic **Container**:

- **Map**: A block whose items all carry explicit string keys.
- **Anonymous Map** (list): A block whose items are all anonymous; semantically its keys are the implicit strings `"0"`, `"1"`, `"2"`, ... assigned in order of appearance.

This integer-like keying is a **semantic model only**. This specification does not prescribe how an implementation stores an anonymous map; see § 5.2.

### 4.2. Block Parsing

A single parsing procedure handles all blocks, parameterized by the effective separator tokens:

- **Block structure**: A block is an `LBRACE`, a sequence of items separated by `ITEM_SEP`, and the matching `RBRACE`. The document root in the indentation surface is a block whose braces are the implicit start and end of the document.
- **Ambiguity resolution**: The parser must look ahead at the first item in the block.
  - If the item follows the pattern `key KV_SEP value`, the block is parsed as a **Map**.
  - If the item is a bare `value`, the block is parsed as an **Anonymous Map**.
  - *Constraint*: A single block cannot mix keyed and anonymous items.
  - *Empty block*: An empty block is an empty Map. It cannot be written when `LBRACE` and `RBRACE` are event realizers (§ 3.4).
- **Anonymous maps of maps**: If a block opens with two consecutive `LBRACE` tokens (the indentation surface's "extra level", or the BRACE style's literal `{{`), the block is an anonymous map whose items are themselves maps. In the indentation surface, consecutive anonymous map items are separated by exactly one blank line (a pair of consecutive `ITEM_SEP` tokens) at the deeper level; scalar items, if present, sit at the intermediate level.
- **Duplicate keys**: A duplicate key within the same map must raise a `SyntaxError` (see § 6).

### 4.3. Unbound Characters

A character consumed by no token — by no realizer, by no reserved symbol, and not as part of a bare lexical run — is not data: outside a string it must raise a `SyntaxError`. A literal `{` in a document whose `LBRACE` is an event realizer is the usual case. The diagnostic should state that the character can be bound as a realizer, or that the BRACE style accepts it.

Line structure is significant only as far as the effective surface binds it: in the explicit surface it is insignificant unless a realizer observes it.

## 5. Interpreter / Data Conversion

### 5.1. Native Type Mapping

The interpreter maps FlexConf types to host language types:

- **Map** -> Dictionary / Hash / Object
- **Anonymous Map (List)** -> Array / Vector / List
- **String** -> String
- **Integer** -> Integer / Long / BigInt
- **Float** -> Float / Double
- **Boolean** -> Boolean
- **Null** -> Null / None / Nil
- **Offset date-time** (`@1979-05-27T07:32:00Z`) -> timezone-aware date-time type
- **Local date-time** (`@1979-05-27T07:32:00`) -> naive date-time type
- **Local date** (`@1979-05-27`) -> date type
- **Local time** (`@07:32:00`) -> time type

### 5.2. Anonymous Map Construction

The implicit keys `"0"`, `"1"`, `"2"`, ... of an anonymous map are a conceptual device of the language semantics. This specification does **not** require any particular intermediate representation:

- **Recommended**: Implementations should construct the host language's ordered array/list type directly from the sequence of items, without materializing the implicit keys at all.
- Implementations in host languages that lack an ordered sequence type may represent an anonymous map as a map with the string keys `"0"` .. `"n-1"` as an equivalent form.

Whether a parsed block becomes a map or an anonymous map is decided solely by the *form of its items* (keyed vs. anonymous), never by inspecting key values — explicit numeric bare keys such as `0:` produce the string key `"0"` in a perfectly ordinary map.

## 6. Error Handling

The parser must provide descriptive error messages including:

- **Error Type**: (e.g., `SyntaxError`, `IndentationError`, `InvalidSurfaceError`)
- **Location**: Line number and Column number.
- **Context**: A snippet of the code where the error occurred.

### Common Errors

- **Unbound Character Error**: "Character '{' is bound by no realizer at line X; bind it or use the BRACE style."
- **Indentation Error**: "Unindent does not match any outer indentation level at line Y."
- **Key Error**: "Duplicate key 'server' found at line Z."
- **Surface Error**: "Invalid surface: LBRACE 'x' and KVSEP 'x' are the same literal realizer."
- **Undetermined Token Error**: "',' is undetermined: ITEMSEP = ',' reads [1,2], KVSEP = ',' reads {\\"1\\":2}; declare one with `#?>`."

## 7. Surface Object and Pragma Processing

To support a configurable surface syntax:

1. **Surface Object**: The parser maintains the realizer of each of the four tokens:
    - `KVSEP`: default `Literal(":")`
    - `ITEMSEP`: default `Literal(",")` (or `<NEWLINE>`)
    - `LBRACE`: default `Literal("{")` (or `<INDENT>`)
    - `RBRACE`: default `Literal("}")` (or `<DEDENT>`)
2. **Style Presets**: The named styles BRACE (all defaults) and INDENT (`LBRACE = <INDENT>`, `RBRACE = <DEDENT>`, `ITEMSEP = <NEWLINE>`, `KVSEP = Literal(":")`) are atomic bindings applied by `SET STYLE`.
3. **Pragma Processor**: For each `#?> SET ...` directive at the head of the file, update the surface in order of appearance; `SET STYLE <name>` first resets the four tokens to the named preset. The final surface must be validated before tokenization.
4. **Surface Validation**: Reject an invalid surface before parsing: the literal realizers must be pairwise distinct and must not equal the `#` comment marker or share a prefix with it; no literal realizer may contain `@` or `!`; an event realizer must be bound to the token it realizes, with `<INDENT>` / `<DEDENT>` bound as a pair.
5. **Dynamic Tokenization**: The lexer must match tokens from the surface object (including multi-character literal realizers) under the matching order of § 3.5, rather than using hardcoded characters.

---

Copyright © 2025 FlexConf Foundation. All rights reserved.
