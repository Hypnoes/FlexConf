# FlexConf 1.0 Specification

*Version 0.0.1-snapshot*
*Published on November 24, 2025*

## Overview

FlexConf is a configuration file format designed for simplicity and flexibility. FlexConf supports two syntax modes that are semantically equivalent: indentation mode and bracket mode. Documents may use either syntax mode, but not both within the same document.

Although this design has basically taken shape, there are still some details under consideration and it will continue to evolve until it is finally finalized.

## Objectives

FlexConf aims to be:

- **Simple**: Minimal syntax with clear rules
- **Flexible**: Multiple syntax options for different use cases
- **Unambiguous**: Explicit structure with well-defined parsing rules
- **Interoperable**: Easy conversion to and from other data formats

## Specification

### File Requirements

- FlexConf files must be valid UTF-8 encoded Unicode documents.
- A FlexConf file must use exclusively one syntax mode (indentation or bracket).
- Syntax mode is determined by the first non-whitespace, non-comment character in the document:
  - If the first character is `{`, the document uses bracket mode
  - Otherwise, the document uses indentation mode

### Comments

- Comments begin with `#` and continue to the end of the line.
- Comments may appear on their own line or after values on the same line.
- Comments are ignored by parsers.

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

- **Maps**: Collections of key/value pairs
- **Lists**: Ordered sequences of values

### Keys

- Keys may be bare identifiers or quoted identifiers.
- **Bare identifiers** may only contain ASCII letters, digits, underscores, and hyphens (`A-Za-z0-9_-`).
- **Quoted identifiers** are enclosed in backticks (`` ` ``) and may contain any valid Unicode character except unescaped backticks.
- Keys that contain characters not permitted in bare identifiers must be quoted.

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

### Collections

#### Maps

A map is a collection of key-value pairs. Maps are defined differently in each syntax mode.

**Indentation Mode Maps**:

```flexconf
server:
  host: "localhost"
  port: 8080
  ssl: false
```

**Bracket Mode Maps**:

```flexconf
{
  server: {
    host: "localhost",
    port: 8080,
    ssl: false
  }
}
```

#### Lists

A list is an ordered sequence of values. Lists are defined differently in each syntax mode.

**Indentation Mode Lists**:

```flexconf
protocols:
    name: "http"
    port: 8080

    name: "https"
    port: 443
  
  9000
  "10010-10015"
```

Note: &lt;indent+&gt; value... &lt;indent-&gt; forms a list. The \n within the list serves as element separation. &lt;indent+&gt; key:value ... &lt;indent-&gt; forms an anonymous Map. According to this semantics, anonymous elements between lists use \n&lt;indent-&gt;\n&lt;indent+&gt; sequence to mark the separation of anonymous Maps between lists. The element semantics, in order, are: end of key-value pair (\n), end of anonymous Map, end of list element, start of anonymous Map.
Consider it in following forms:

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

but the key is hidden and auto generated. That's explain why Maps inside a List should have extra indents.

**Bracket Mode Lists**:

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

#### Mixed Collections

Maps and lists can be nested within each other in both syntax modes.

**Indentation Mode Example**:

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

**Bracket Mode Example**:

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

### Syntax Modes

#### Indentation Mode

- Uses spaces for indentation (tabs are not permitted).
- The first non-zero indent level defines the base indent unit for the document.
- All indent levels must be multiples of the base indent unit.
- Maps are defined by key-value pairs at the same indentation level.
- Lists are defined by value only items at the same indentation level.
- New line separate items within both maps and lists (trailing newline are not permitted).
- Nested structures are indicated by increased indentation.

#### Bracket Mode

- Uses braces `{}` to denote blocks (both Maps and Lists).
- Maps are distinguished by the presence of key-value pairs: `{ key: value }`.
- Lists are distinguished by the presence of values only: `{ item1, item2 }`.
- A List of Maps appears as double braces: `{{ key: value }}` (Outer brace for List, inner for Map).
- Commas separate items within both maps and lists (trailing commas are permitted).
- Whitespace is insignificant except within strings.

### Conversions Between Modes

- Documents in either syntax mode can be converted to the other mode without loss of information.
- The conversion must preserve all data and structure.
- Comments may be relocated but must be preserved.

### Validity Rules

The following conditions make a FlexConf document invalid:

1. **Mixed syntax modes**: Using both indentation and bracket syntax in the same document.
2. **Invalid indentation**:
   - Using tabs for indentation in indentation mode
   - Non-uniform indentation levels (not multiples of base indent)
3. **Mixed key types in collections**: In a single collection, items must either all have explicit keys or all be list items. Mixing is not permitted.
4. **Duplicate keys**: A map cannot contain duplicate keys at the same level.
5. **Incorrect list item separation**:
   - In indentation mode: missing blank lines between list items or extra blank lines
   - In bracket mode: missing commas between list items
6. **Unmatched braces**: In bracket mode, all opening braces must have matching closing braces.

### Filename Extension

- FlexConf files should use the extension `.fc`.

### MIME Type

- The MIME type for FlexConf files is `application/flexconf`.

## Extensibility

FlexConf is designed with future extensibility in mind, allowing for customization of syntax elements through special pragma comments at the beginning of the document.

### Pragma Directives

Pragmas start with `#?>` and allow users to redefine core syntax delimiters for the current file. This enables the language to adapt to different preferences or constraints without changing the underlying parser logic.

Examples of potential future directives:

```flexconf
#?> SET SPLITER ';'
#?> SET BLOCKIDENTIFER '<' '>'
```

### Future Customization Goals

The extensibility roadmap includes support for customizing:

- **Block Identifiers**: Replacing curly braces `{}` with square brackets `[]`, parentheses `()`, or other paired sequences. Indentation is treated conceptually as a special kind of bracket.
- **Key-Value Separators**: Defining alternatives to the colon `:`, such as equals `=`, spaces, or other symbols.
- **Sequence Separators**: Configuring the item separator, such as using semicolons `;` instead of newlines or commas.

This design ensures that while the core structure (hierarchical key-value pairs) remains consistent, the surface syntax can evolve or be tailored to specific needs.

## Formal Grammar

A formal ABNF grammar for FlexConf is available in [FlexConf ABNF Grammar SPEC](./FlexConf%20ABNF%20Grammar%20SPEC.md).

---

Copyright © 2025 Hypnoes Liu. All rights reserved.
This specification is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.
