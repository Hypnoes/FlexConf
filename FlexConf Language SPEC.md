# FlexConf 1.0 Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 8, 2026*

## Overview

FlexConf is a configuration file format designed for simplicity and flexibility. FlexConf is defined by a **single unified structural model**: every document is a hierarchy of *blocks* of items, and the concrete surface syntax of a document is governed by five configurable **syntax parameters** (§ Syntax Parameters). Two canonical parameter configurations, called **styles**, are predefined:

- the **BRACE** style (braces and commas, JSON-like), and
- the **INDENT** style (significant indentation and newlines, YAML-like).

Both styles express exactly the same data model, and documents may redefine individual parameters through pragma directives (§ Pragma Directives). A document uses exactly one surface style throughout.

## Objectives

FlexConf aims to be:

- **Simple**: Minimal syntax with clear rules
- **Flexible**: Configurable surface syntax for different use cases
- **Unambiguous**: Explicit structure with well-defined parsing rules
- **Interoperable**: Easy conversion to and from other data formats

## Specification

### File Requirements

- FlexConf files must be valid UTF-8 encoded Unicode documents.
- A FlexConf document uses exactly one surface style (see § Style Resolution and Surface Detection).

### Syntax Parameters

The surface syntax of a FlexConf document is determined by five parameters:

| Parameter | Default | Legal values | Meaning |
| --- | --- | --- | --- |
| `KeyValueSeparator` | `:` | literal string | Separates a key from its value |
| `ItemSeparator` | `,` | literal string or `<NEWLINE>` | Separates adjacent items within a block |
| `LeftBrace` | `{` | literal string or `<INDENT>` | Opens a block |
| `RightBrace` | `}` | literal string or `<DEDENT>` | Closes a block |
| `CommentMarker` | `#` | `#` or `//` only | Starts a line comment |

**Literal values** are quoted strings of one or more characters.

**Symbolic values** denote virtual tokens produced by line-structure analysis rather than literal characters:

- `<INDENT>`: an increase of one indentation level (conceptually the `<tab>` of the line-oriented surface)
- `<DEDENT>`: a decrease of one indentation level (conceptually the `<bs>`)
- `<NEWLINE>`: a line ending

A configuration is **valid** only if:

1. The literal values of `KeyValueSeparator`, `ItemSeparator`, `LeftBrace`, and `RightBrace` are pairwise distinct, non-empty, and contain no whitespace or string quote characters.
2. No literal separator is a prefix of `CommentMarker`, and `CommentMarker` is not a prefix of any literal separator.
3. `<INDENT>` and `<DEDENT>` are bound as a pair: `LeftBrace = <INDENT>` if and only if `RightBrace = <DEDENT>`.
4. `KeyValueSeparator` and `CommentMarker` are always literal.

An invalid configuration raises an *Invalid Configuration Error* before any parsing takes place.

### Styles

A **style** is a named preset of the syntax parameters.

#### BRACE (default style)

```text
KeyValueSeparator = ':'
ItemSeparator     = ','
LeftBrace         = '{'
RightBrace        = '}'
CommentMarker     = '#'
```

All whitespace (spaces, tabs, newlines) is insignificant between tokens in this style (see § Whitespace Handling).

#### INDENT

`SET STYLE INDENT` is exactly equivalent to the following bindings (`CommentMarker` unchanged):

```text
LeftBrace         = <INDENT>
RightBrace        = <DEDENT>
ItemSeparator     = <NEWLINE>
KeyValueSeparator = ':'
```

The INDENT style adds the following rules, which are part of its virtual-token generation:

- Only spaces are used for indentation; tabs are not permitted.
- The base indent unit is the greatest common divisor of all non-zero indentation levels in the document; every indentation width must be a multiple of it.
- Each indentation level generates exactly one `<INDENT>` / `<DEDENT>` virtual token, so a jump of two levels produces two consecutive `LeftBrace` tokens (see § Anonymous Maps).
- A blank line produces an extra `ItemSeparator` token; exactly one blank line separates adjacent anonymous map items (see § Anonymous Maps).

Individual parameters may be overridden on top of a style (e.g. `SET STYLE INDENT` followed by `SET CommentMarker '//'`). Such mixed bindings are legal as long as the final configuration satisfies the validity constraints above, but are unconventional.

### Comments

- Comments begin with the effective `CommentMarker` and continue to the end of the line.
- Comments may appear on their own line or after values on the same line.
- Comments are ignored by parsers; a comment-only line produces no tokens.
- The default comment marker is `#`; it can be switched to `//` per document via `#?> SET CommentMarker '//'`.
- When `//` is the comment marker, a `/` encountered where a token is expected must be the start of a `//` comment; a lone `/` outside a string is a `SyntaxError`. (Bare keys and bare literals never contain `/`, so this introduces no ambiguity.)
- The pragma prefix `#?>` is fixed meta-syntax and does not change with `CommentMarker` (see § Pragma Directives).

```flexconf
# This is a full-line comment
key: "value"  # This is a comment at the end of a line
```

### Data Types

#### Primitives

FlexConf supports the following primitive values:

- **Strings**:
  - Double-quoted basic strings: `"string"`
  - Single-quoted literal strings: `'string'`
  - Triple-quoted multi-line strings: `"""string"""`

- **Numbers**:
  - Integers: `42`, `-17`
  - Floats: `3.14`, `-0.01`, `5e+22`, `+inf`, `-inf`, `nan`
  - Hexadecimal: `0xDEADBEEF`, `0xdead_beef`
  - Octal: `0o755`
  - Binary: `0b11010110`

- **Booleans**: `true` and `false`
- **Null**: `null`

#### Collections

- **Maps**: Blocks in which every item has an explicit key.
- **Anonymous Maps** (traditionally called *lists*): Blocks in which every item is a bare value; see § Anonymous Maps.

### Keys

- Keys may be bare identifiers or quoted identifiers.
- **Bare identifiers** may only contain ASCII letters, digits, underscores, and hyphens (`A-Za-z0-9_-`).
- **Quoted identifiers** are enclosed in backticks (`` ` ``) and may contain any valid Unicode character except unescaped backticks.
- Keys that contain characters not permitted in bare identifiers must be quoted.
- All keys are strings. A bare key that looks like a number (e.g. `0`, `42`) is the *string* `"0"`, `"42"`.

```flexconf
bare_key: "value"
`quoted_key`: "value"
`key.with.dots`: "value"
`key with spaces`: "value"
```

### Values

#### Strings

FlexConf supports four ways to express strings:

1. **Basic strings** are surrounded by double quotes. Special characters must be escaped.

   ```flexconf
   str: "I'm a string. \"You can quote me\". Name\tJosé\nLocation\tSF."
   ```

2. **Multi-line basic strings** are surrounded by three double quotes and allow newlines.

   ```flexconf
   str1: """
   Roses are red
   Violets are blue"""
   ```

3. **Literal strings** are surrounded by single quotes. No escaping is processed.

   ```flexconf
   winpath: 'C:\Users\nodejs\templates'
   ```

4. **Multi-line literal strings** are surrounded by three single quotes.

   ```flexconf
   regex2: '''I [dw]on't need \d{2} apples'''
   ```

#### Numbers

Both integers and floating point numbers are supported.

```flexconf
int1: +99
int2: 42
int3: -17
flt1: +1.0
flt2: 3.1415
flt3: -0.01
flt4: 5e+22
special1: +inf
special2: -inf
special3: nan
```

Underscores may be used to enhance readability:

```flexconf
int4: 1_000
flt5: 224_617.445_991_228
```

#### Booleans and Null

```flexconf
bool1: true
bool2: false
nothing: null
```

### Block Structure

Every FlexConf document is built from a single abstract block rule, parameterized by the syntax parameters:

```text
block = LeftBrace *(item ItemSeparator) [item] [ItemSeparator] RightBrace
item  = key KeyValueSeparator value    ; keyed item
      / value                          ; anonymous item
```

- A block whose items are all **keyed** is a **Map**.
- A block whose items are all **anonymous** is an **Anonymous Map** (see below).
- Mixing keyed and anonymous items in the same block is invalid.
- A trailing `ItemSeparator` after the last item is permitted in the BRACE style.
- An empty block (e.g. `{}`) is ambiguous and defaults to an empty Map.

### Collections

#### Maps

A map is a block of key-value pairs.

**BRACE style**:

```flexconf
{
  server: {
    host: "localhost",
    port: 8080,
    ssl: false
  }
}
```

**INDENT style**:

```flexconf
server:
  host: "localhost"
  port: 8080
  ssl: false
```

Note that in the INDENT style the block following a key is delimited by virtual `<INDENT>` / `<DEDENT>` tokens and items are separated by newlines — the abstract block rule is unchanged.

#### Anonymous Maps

An anonymous map is a block whose items are bare values. Semantically it is a map whose keys are implicit strings `"0"`, `"1"`, `"2"`, ..., assigned in order of appearance. This is a **semantic model**, not an implementation requirement: to the host language an anonymous map is simply an ordered sequence (an array), and parsers are expected to construct one directly.

Whether a block is a map or an anonymous map is decided by the **form of its items**, never by key values: an item written with a key makes the block a map; an item written without one makes it anonymous. Since the implicit keys `"0"`, `"1"`, ... coincide with the strings produced by explicit numeric bare keys, the following two documents are equivalent *at the data level*:

```flexconf
protocols:
  0:
    name: "http"
    port: 8080
  1:
    name: "https"
    port: 443
  2: 9000
  3: "10010-10015"
```

is the explicit-key form of the anonymous map below — but the first document is a *map* (its keys were written), while the second is an *anonymous map* (its keys are implicit):

```flexconf
protocols:
    name: "http"
    port: 8080

    name: "https"
    port: 443
  9000
  "10010-10015"
```

**Anonymous map items in the INDENT style**:

- **Scalar items** appear at the block's first indentation level (the *list level*), one value per line.
- **Map items** are anonymous maps whose key-value pairs sit one indentation level deeper than the list level. This extra indentation level is required: it distinguishes the key-value pairs of a map item from the key-value pairs of the enclosing map. Consequently, when the first content line of an indented block is two indentation levels deeper than its key (two consecutive `<INDENT>` tokens), the block is an anonymous map whose map items occupy the deeper level.
- **Adjacent map items are separated by exactly one blank line.** The newline after the last key-value pair ends that pair, and the blank line ends the current map item; the next map item begins at the same deeper indentation level.
- Scalar items and map items may coexist in the same anonymous map, as shown in the example above.

**Anonymous maps in the BRACE style**:

```flexconf
{
  protocols: {
    { name: "http", port: 8080 },
    { name: "https", port: 443 },
    9000,
    "10010-10015"
  }
}
```

An anonymous map of maps appears as double braces: the outer pair delimits the anonymous map, each inner pair delimits one map item.

#### Mixed Collections

Maps and anonymous maps can be nested within each other in every style.

**INDENT style example**:

```flexconf
application:
  name: "DataProcessor"
  version: "1.0"
  servers:
      host: "localhost"
      port: 8080

      host: "production.example.com"
      port: 443

  settings:
    debug: true
    timeout: 30
```

**BRACE style example**:

```flexconf
{
  application: {
    name: "DataProcessor",
    version: "1.0",
    servers: {
      {
        host: "localhost",
        port: 8080
      },
      {
        host: "production.example.com",
        port: 443
      }
    },
    settings: {
      debug: true,
      timeout: 30
    }
  }
}
```

### Style Resolution and Surface Detection

The effective configuration of a document is resolved as follows:

1. **Pragma scanning**: The lexer scans the head of the file for pragma directives (§ Pragma Directives) and applies them in order of appearance. `SET STYLE <name>` binds the four structural parameters atomically; subsequent single-parameter `SET` directives override individual parameters.
2. **Surface detection**: After skipping whitespace and comments (using the effective `CommentMarker`), the first non-whitespace, non-comment character is examined:
   - If `LeftBrace` is bound to a literal and the text at that position starts with it, the document uses the **explicit block surface** (physical braces).
   - Otherwise the document uses the **indentation surface**, which requires `LeftBrace = <INDENT>`; if the effective configuration does not satisfy this, the document is invalid.
   - As a backward-compatible convenience, a document with **no pragma directives and no explicit configuration** behaves as if its style were auto-detected: a leading `{` selects BRACE, anything else selects INDENT.
3. **Immutability**: Once the surface is determined, it cannot change within the document. In the indentation surface, encountering a literal `{` or `}` outside a string is a `SyntaxError` (these are the BRACE style's braces, and styles never mix).

### Whitespace Handling

**General rule**: a whitespace character is syntactically significant if and only if the effective configuration binds it to a syntactic role. Unbound whitespace is meaningless, and lexers skip it between tokens.

- In the default BRACE style all four structural parameters are literals, so spaces, tabs, and newlines are all insignificant between tokens: documents may be reflowed and aligned freely.
- `ItemSeparator = <NEWLINE>` makes line endings significant (they *are* the separator), and two consecutive line endings form a blank line, which ends an anonymous map item in the INDENT style.
- `LeftBrace = <INDENT>` / `RightBrace = <DEDENT>` make the leading whitespace of each line significant (it generates virtual tokens); whitespace within a line remains insignificant.
- Whitespace inside string values is always significant.
- Comments run from the `CommentMarker` to the end of the line; comment-only lines produce no tokens. A blank line produces an `ItemSeparator` token when `ItemSeparator = <NEWLINE>`.

### Conversions Between Styles

- Documents in any style can be converted to another style without loss of information, provided the target style can express the same data.
- The conversion must preserve all data and structure.
- Comments may be relocated but must be preserved.

### Pragma Directives

Pragmas start with `#?>` and redefine syntax parameters for the current file. The pragma prefix is fixed meta-syntax: it is always `#?>`, regardless of the configured `CommentMarker`, because pragmas are processed before the configuration takes effect.

Pragmas must appear at the very beginning of the document, preceded only by whitespace, blank lines, or `#` comments. Two directive forms exist:

```flexconf
#?> SET STYLE INDENT           " named preset: binds the four structural parameters atomically
#?> SET STYLE BRACE            " the default style; may be omitted
#?> SET ItemSeparator ';'      " single-parameter override
#?> SET LeftBrace '['
#?> SET RightBrace ']'
#?> SET LeftBrace <INDENT>     " symbolic values may also be set individually
#?> SET CommentMarker '//'     " switch the comment marker
```

Rules:

- Directives apply in order of appearance; later directives override earlier ones.
- A single-parameter value is either a quoted string or one of the symbolic values `<INDENT>`, `<DEDENT>`, `<NEWLINE>`. `CommentMarker` accepts only `'#'` and `'//'`.
- `STYLE` accepts the style names `BRACE` and `INDENT` (case-sensitive).
- An unknown parameter name, unknown style name, or illegal value is a `SyntaxError`.
- All pragmas take effect before surface detection.

### Validity Rules

The following conditions make a FlexConf document invalid:

1. **Mixed surfaces**: Using literal block braces in the indentation surface, or more than one surface style in the same document.
2. **Invalid indentation** (INDENT style):
   - Using tabs for indentation
   - Non-uniform indentation levels (not multiples of the base indent unit)
3. **Mixed item forms in a block**: In a single block, items must either all have explicit keys or all be anonymous. Mixing is not permitted.
4. **Duplicate keys**: A map cannot contain duplicate keys at the same level.
5. **Incorrect item separation**:
   - In the INDENT style: missing blank lines between anonymous map items, or extra blank lines
   - In the BRACE style: missing `ItemSeparator` between items
6. **Unmatched braces**: Every `LeftBrace` (literal or virtual) must have a matching `RightBrace`.
7. **Invalid configuration**: A pragma or configuration that violates the constraints in § Syntax Parameters (unknown names, conflicting separators, unpaired `<INDENT>`/`<DEDENT>`, illegal `CommentMarker`, ...).

### Filename Extension

- FlexConf files should use the extension `.fc`.

### MIME Type

- The MIME type for FlexConf files is `application/flexconf`.

## Formal Grammar

A formal ABNF grammar for FlexConf is available in [FlexConf ABNF Grammar SPEC](./FlexConf%20ABNF%20Grammar%20SPEC.md).

---

Copyright © 2025 FlexConf Foundation. All rights reserved.
This specification is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.
