# FlexConf Parser Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 8, 2026*

## 1. Introduction

This document specifies the requirements and architectural design for a compliant FlexConf parser and interpreter. It details the process of converting FlexConf source text into a data structure and vice versa, ensuring consistent behavior across different implementations.

FlexConf has a single unified structural model whose surface syntax is governed by five configurable parameters (`KeyValueSeparator`, `ItemSeparator`, `LeftBrace`, `RightBrace`, `CommentMarker`) and two canonical style presets (BRACE and INDENT). This specification describes a single parsing pipeline parameterized by that configuration; there are no separate "indentation parser" and "bracket parser".

## 2. Architecture Overview

A FlexConf implementation typically consists of three main components:

1. **Lexer (Tokenizer)**: Converts the raw character stream into a sequence of tokens, guided by the effective configuration.
2. **Parser**: Consumes tokens to build an Abstract Syntax Tree (AST) or intermediate representation, enforcing grammatical rules.
3. **Interpreter/Loader**: Converts the AST into native data structures (e.g., HashMaps, Arrays, Objects) for the host language.

## 3. Lexical Analysis

### 3.1. Input Processing

- The input must be a UTF-8 encoded stream.
- **Pragma Scanning**: Before standard tokenization, the lexer must scan the beginning of the file for pragma directives (`#?>`). The pragma prefix is fixed meta-syntax and does not change with `CommentMarker`. Pragmas are applied in order of appearance — `SET STYLE <name>` binds the four structural parameters atomically, subsequent single-parameter `SET` directives override individual values — and the resulting configuration is validated (§ 7) before any further processing. Unknown parameter names, unknown style names, and illegal values are `SyntaxError`s.

### 3.2. Style Resolution and Surface Detection

The lexer must resolve the effective configuration and the document's surface before processing the first data token.

- **Algorithm**: After pragma scanning, skip all leading whitespace and comments (using the effective `CommentMarker`).
  - If `LeftBrace` is a literal and the text at that position starts with it, set the surface to **explicit** (physical braces).
  - Otherwise, the surface is **indentation**; this requires `LeftBrace = <INDENT>` (and hence `RightBrace = <DEDENT>`) in the effective configuration. If the configuration does not satisfy this, raise an `InvalidConfigurationError`.
  - Backward-compatible convenience: a document with no pragmas and no explicit configuration auto-detects — a leading `{` selects the BRACE style, anything else selects the INDENT style.
- **Constraint**: Once the surface is set, it is immutable for the document.

### 3.3. Token Generation

The lexer generates a stream of tokens drawn from a single vocabulary (the names below are advisory, not mandated):

- `IDENTIFIER` (bare keys), `STRING`, `NUMBER`, `BOOLEAN`, `NULL` (literals)
- `KV_SEP` — the effective `KeyValueSeparator`
- `ITEM_SEP` — the effective `ItemSeparator` (a literal token, or a virtual token per line ending when bound to `<NEWLINE>`)
- `LBRACE`, `RBRACE` — the effective braces (literal tokens, or virtual tokens from indentation analysis when bound to `<INDENT>` / `<DEDENT>`)
- `EOF`

Comments produce no tokens. When `CommentMarker` is `//`, a lone `/` outside a string is a `SyntaxError`.

**Whitespace skipping**: whitespace not bound to a syntactic role is skipped between tokens. In the BRACE style this covers all spaces, tabs, and newlines. When `ItemSeparator = <NEWLINE>`, line endings produce `ITEM_SEP` tokens and are not skipped; a blank line therefore produces two consecutive `ITEM_SEP` tokens. When `LeftBrace = <INDENT>`, line-leading spaces feed virtual token generation (§ 3.4) and are not skipped.

### 3.4. Virtual Token Generation (Indentation Surface)

When the indentation surface is active, the lexer derives `LBRACE` / `RBRACE` / `ITEM_SEP` from line structure:

- The lexer maintains a **Stack of Indentation Levels**, initialized with `[0]`.
- **Base Unit Detection**: Before tokenization, the lexer scans the document and computes the `Base Indent Unit` as the greatest common divisor of all non-zero indentation levels (blank and comment-only lines excluded). Every indentation width must be a multiple of this unit.
- **`LBRACE` emission**: When the indentation level increases, one `LBRACE` token is emitted *per level* (pushing each level onto the stack), so the parser can detect the extra level of anonymous map items (§ 4.2).
- **`RBRACE` emission**: When the indentation level decreases, one `RBRACE` per level is emitted (popping the stack).
  - *Error*: If the new level does not match a level on the stack, raise an `IndentationError`.
- **`ITEM_SEP` emission**: Each line ending produces one `ITEM_SEP`. Comment-only lines generate no tokens. Blank lines generate `ITEM_SEP` tokens (a blank line therefore yields a pair of consecutive `ITEM_SEP`s, which ends an anonymous map item, § 4.2); a blank line that precedes a dedent is emitted at the level whose items it separates.

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
  - *Empty block*: An empty block (e.g. `{}`) is ambiguous and defaults to an empty Map.
- **Anonymous maps of maps**: If a block opens with two consecutive `LBRACE` tokens (the indentation surface's "extra level", or the BRACE style's literal `{{`), the block is an anonymous map whose items are themselves maps. In the indentation surface, consecutive anonymous map items are separated by exactly one blank line (a pair of consecutive `ITEM_SEP` tokens) at the deeper level; scalar items, if present, sit at the intermediate level.
- **Duplicate keys**: A duplicate key within the same map must raise a `SyntaxError` (see § 6).

### 4.3. Surface Consistency Enforcement

The parser and lexer must enforce the "no mixed surfaces" rule:

- In the **indentation surface**, encountering the BRACE style's literal braces (`{`, `}`) outside of a string is a `SyntaxError`.
- In the **explicit surface**, indentation and line structure are insignificant unless bound by the configuration.

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

### 5.2. Anonymous Map Construction

The implicit keys `"0"`, `"1"`, `"2"`, ... of an anonymous map are a conceptual device of the language semantics. This specification does **not** require any particular intermediate representation:

- **Recommended**: Implementations should construct the host language's ordered array/list type directly from the sequence of items, without materializing the implicit keys at all.
- Implementations in host languages that lack an ordered sequence type may represent an anonymous map as a map with the string keys `"0"` .. `"n-1"` as an equivalent form.

Whether a parsed block becomes a map or an anonymous map is decided solely by the *form of its items* (keyed vs. anonymous), never by inspecting key values — explicit numeric bare keys such as `0:` produce the string key `"0"` in a perfectly ordinary map.

## 6. Error Handling

The parser must provide descriptive error messages including:

- **Error Type**: (e.g., `SyntaxError`, `IndentationError`, `InvalidConfigurationError`)
- **Location**: Line number and Column number.
- **Context**: A snippet of the code where the error occurred.

### Common Errors

- **Mixed Surface Error**: "Found literal brace '{' in an indentation-surface document at line X."
- **Indentation Error**: "Unindent does not match any outer indentation level at line Y."
- **Key Error**: "Duplicate key 'server' found at line Z."
- **Configuration Error**: "Invalid configuration: ItemSeparator ';' conflicts with KeyValueSeparator."

## 7. Configuration Object and Pragma Processing

To support configurable surface syntax:

1. **Configuration Object**: The parser maintains a configuration state containing the five parameters:
    - `KeyValueSeparator`: default `:`
    - `ItemSeparator`: default `,` (or the symbolic value `<NEWLINE>`)
    - `LeftBrace`: default `{` (or `<INDENT>`)
    - `RightBrace`: default `}` (or `<DEDENT>`)
    - `CommentMarker`: default `#` (the only other legal value is `//`)
2. **Style Presets**: The named styles BRACE (all defaults) and INDENT (`LeftBrace = <INDENT>`, `RightBrace = <DEDENT>`, `ItemSeparator = <NEWLINE>`, `KeyValueSeparator = :`) are atomic bindings applied by `SET STYLE`.
3. **Pragma Processor**: For each `#?> SET ...` directive at the head of the file, update the configuration in order of appearance; `SET STYLE <name>` first resets the four structural parameters to the named preset. The final configuration must be validated before tokenization.
4. **Configuration Validation**: Reject conflicting configurations before parsing: literal separators must be pairwise distinct and conflict-free with `CommentMarker`; `<INDENT>` / `<DEDENT>` must be bound as a pair; `CommentMarker` must be `#` or `//`.
5. **Dynamic Tokenization**: The lexer must use the values from the configuration object to match tokens (including multi-character literal separators), rather than hardcoded characters.

---

Copyright © 2025 FlexConf Foundation. All rights reserved.
