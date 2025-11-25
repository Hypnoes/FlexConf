# FlexConf Parser Specification

*Version 0.0.1-snapshot*
*Published on November 24, 2025*

## 1. Introduction

This document specifies the requirements and architectural design for a compliant FlexConf parser and interpreter. It details the process of converting FlexConf source text into a data structure and vice versa, ensuring consistent behavior across different implementations.

Although this design has basically taken shape, there are still some details under consideration and it will continue to evolve until it is finally finalized.

## 2. Architecture Overview

A FlexConf implementation typically consists of three main components:

1. **Lexer (Tokenizer)**: Converts the raw character stream into a sequence of tokens.
2. **Parser**: Consumes tokens to build an Abstract Syntax Tree (AST) or intermediate representation, enforcing grammatical rules.
3. **Interpreter/Loader**: Converts the AST into native data structures (e.g., HashMaps, Arrays, Objects) for the host language.

## 3. Lexical Analysis

### 3.1. Input Processing

- The input must be a UTF-8 encoded stream.
- **Pragma Scanning**: Before standard tokenization, the lexer must scan the beginning of the file for Pragma Directives (`#?>`). These directives may alter the lexer's configuration (e.g., changing delimiters) for the remainder of the file.

### 3.2. Mode Detection

The lexer must determine the syntax mode before processing the first data token.

- **Algorithm**: Skip all leading whitespace and comments.
  - If the first character is `{` (or the configured Block Start Identifier), set mode to **Bracket Mode**.
  - Otherwise, set mode to **Indentation Mode**.
- **Constraint**: Once the mode is set, it is immutable for the document.

### 3.3. Token Generation

The lexer generates a stream of tokens. Common tokens include:

- `IDENTIFIER` (bare keys)
- `STRING`, `NUMBER`, `BOOLEAN`, `NULL` (literals)
- `COLON` (`:`)
- `LBRACE` (`{`), `RBRACE` (`}`) - *Bracket Mode only*
- `COMMA` (`,`) - *Bracket Mode only*
- `NEWLINE` (`\n`) - *Indentation Mode separator*
- `INDENT`, `DEDENT` - *Indentation Mode structural tokens*

### 3.4. Indentation Handling (Indentation Mode)

- The lexer maintains a **Stack of Indentation Levels**, initialized with `[0]`.
- **Base Unit Detection**: The first line with indentation > 0 defines the `Base Indent Unit`. All subsequent indentations must be a multiple of this unit.
- **INDENT Token**: Emitted when the indentation level increases. Push new level to stack.
- **DEDENT Token**: Emitted when the indentation level decreases. Pop from stack.
  - *Error*: If the new level does not match the level now at the top of the stack, raise an `IndentationError`.
- **Ignored Lines**: Blank lines and comment-only lines do not generate `INDENT`/`DEDENT` tokens but may generate `NEWLINE` tokens if significant for list separation.

## 4. Parsing Strategy

### 4.1. Unified Container Model

Per the language design, FlexConf treats Maps and Lists as variations of a generic **Container**.

- **Map**: A Container with explicit string keys.
- **List**: A Container with implicit, auto-incrementing integer keys (0, 1, 2...).

### 4.2. Indentation Mode Parsing

- **Block Structure**: A block is defined by an `INDENT` token, a sequence of items, and a `DEDENT` token.
- **Item Separation**: Items are separated by `NEWLINE` tokens.
- **Ambiguity Resolution**:
  - If a line follows the pattern `key : value`, it is parsed as a Map entry.
  - If a line contains only a `value`, it is parsed as a List item.
  - *Constraint*: A single block cannot mix explicit keys and implicit keys.

### 4.3. Bracket Mode Parsing

- **Block Structure**: A block is enclosed by `{` and `}`.
- **Item Separation**: Items are separated by `,`.
- **Ambiguity Resolution**:
  - The parser must look ahead at the first item in the block.
  - If the item follows the pattern `key : value`, the block is parsed as a **Map**.
  - If the item is a `value` (and not followed by `:`), the block is parsed as a **List**.
  - *Constraint*: A single block cannot mix explicit keys and implicit keys (values).
  - *Empty Block*: An empty block `{}` is ambiguous but typically defaults to an empty Map.

### 4.4. Strict Mode Enforcement

The parser must enforce the "No Mixing" rule:

- In **Indentation Mode**, encountering a `{` (outside of a string) is a `SyntaxError`.
- In **Bracket Mode**, indentation is treated as insignificant whitespace.

## 5. Interpreter / Data Conversion

### 5.1. Native Type Mapping

The interpreter maps FlexConf types to host language types:

- **Map** -> Dictionary / Hash / Object
- **List** -> Array / Vector / List
- **String** -> String
- **Integer** -> Integer / Long / BigInt
- **Float** -> Float / Double
- **Boolean** -> Boolean
- **Null** -> Null / None / Nil

### 5.2. List Construction

Since Lists are conceptually Maps with integer keys:

1. The parser may initially store lists as Maps: `{ "0": val0, "1": val1 }`.
2. The interpreter converts these "Integer-Keyed Maps" into native Array structures for user convenience.

## 6. Error Handling

The parser must provide descriptive error messages including:

- **Error Type**: (e.g., `SyntaxError`, `IndentationError`, `ModeMismatchError`)
- **Location**: Line number and Column number.
- **Context**: A snippet of the code where the error occurred.

### Common Errors

- **Mixed Mode Error**: "Found bracket syntax '{' in an indentation-mode document at line X."
- **Indentation Error**: "Unindent does not match any outer indentation level at line Y."
- **Key Error**: "Duplicate key 'server' found at line Z."

## 7. Extensibility Implementation

To support the "Extensibility" roadmap:

1. **Configuration Object**: The parser should maintain a configuration state containing:
    - `blockStart`: default `{`
    - `blockEnd`: default `}`
    - `separator`: default `,` (bracket mode) or `\n` (indent mode)
    - `keyValueSep`: default `:`
2. **Pragma Processor**: When parsing `#?> SET BLOCKIDENTIFER '[' ']'`, the parser updates the `blockStart` and `blockEnd` in the configuration object.
3. **Dynamic Tokenization**: The Lexer must use the values from the Configuration Object to match tokens, rather than hardcoded characters.

---

Copyright © 2025 Hypnoes Liu. All rights reserved.
