# FlexConf 1.0 Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 12, 2026*

## Overview

FlexConf is a configuration file format designed for simplicity and flexibility. FlexConf is defined by a **single unified structural model**: every document is a hierarchy of *blocks* of items, and the concrete surface syntax of a document is governed by four **structural tokens** whose form is configurable (§ Structural Tokens and Realizers). Two canonical surfaces, called **styles**, are predefined:

- the **BRACE** style (braces and commas, JSON-like), and
- the **INDENT** style (significant indentation and newlines, YAML-like).

Both styles express exactly the same data model, and documents may rebind individual tokens through pragma directives (§ Pragma Directives). A document uses exactly one surface throughout.

## Objectives

FlexConf aims to be:

- **Simple**: Minimal syntax with clear rules
- **Flexible**: Configurable surface syntax for different use cases
- **Unambiguous**: Explicit structure with well-defined parsing rules
- **Interoperable**: Easy conversion to and from other data formats

## Specification

### File Requirements

- FlexConf files must be valid UTF-8 encoded Unicode documents.
- A FlexConf document uses exactly one surface (see § Style Resolution and Surface Detection).

### Structural Tokens and Realizers

Every FlexConf document is tokenized into a fixed vocabulary of four **structural tokens**:

| Token | Role |
| --- | --- |
| `LBRACE` | Opens a block |
| `RBRACE` | Closes a block |
| `KVSEP` | Separates a key from its value |
| `ITEMSEP` | Separates adjacent items of a block |

What differs between documents is not the vocabulary but the **realizer** assigned to each token: the form in which the token reaches the text.

```text
Realizer = Literal(text)            ; a written string, matched literally
         | Event(Indent, Increase)  ; an indentation level is entered
         | Event(Indent, Decrease)  ; an indentation level is left
         | Event(Line)              ; a line ending

Surface  = { LBRACE: Realizer, RBRACE: Realizer, KVSEP: Realizer, ITEMSEP: Realizer }
```

In pragma directives the first component is the token name and the second is either a quoted string or one of three event spellings: `<INDENT>` is `Event(Indent, Increase)`, `<DEDENT>` is `Event(Indent, Decrease)`, and `<NEWLINE>` is `Event(Line)` (§ Pragma Directives). Comments are introduced by `#`; the comment marker is not a structural token.

Two restrictions follow from the roles themselves, not from any additional rule:

- `KVSEP` is always a `Literal`: no layout event separates a key from its value.
- `Event(Indent, Increase)` realizes `LBRACE` only, `Event(Indent, Decrease)` realizes `RBRACE` only, and `Event(Line)` realizes `ITEMSEP` only. The two `Indent` directions are one mechanism and are always bound together.

#### Literal realizers

A literal realizer is a string that:

1. is non-empty, and contains no whitespace, no string quote character (`"`, `'`, `` ` ``), and none of the reserved meta-syntax symbols `@` and `!` (§ Reserved Words and Symbols);
2. is neither a prefix of the comment marker `#` nor prefixed by it;
3. is pairwise distinct from every other literal realizer of the document.

Nothing further is required of it. A literal realizer may overlap the characters that occur inside a bare lexical run, and two literal realizers may stand in a prefix relation with each other; both situations are resolved by the order in which candidates are matched (§ Lexical Boundaries).

#### Event realizers

| Realizer | Produced when |
| --- | --- |
| `Event(Indent, Increase)` | a line is more indented than the line that opened the current block |
| `Event(Indent, Decrease)` | a line is less indented than the current block |
| `Event(Line)` | a line ends |

Three obligations attach to them:

- **Significance.** Line endings are significant exactly when a realizer observes them, and leading whitespace is significant exactly when `LBRACE` and `RBRACE` are realized by `Event(Indent, …)`. All other whitespace between tokens is insignificant.
- **Derivation.** An event token exists only where the document exhibits the corresponding geometry. A construct that produces no geometry produces no token, so an empty block has no representation when `LBRACE` and `RBRACE` are realized by `Event(Indent, …)` (§ Conversions).
- **Repetition.** Two consecutive `Event(Line)` items are structural: they end the current item of an anonymous map (§ Anonymous Maps). A literal `ITEMSEP` carries no repeated-token meaning.

#### Styles

A **style** is a named surface. Two styles are predefined.

BRACE (default):

```text
LBRACE  = Literal("{")
RBRACE  = Literal("}")
KVSEP   = Literal(":")
ITEMSEP = Literal(",")
```

INDENT (`SET STYLE INDENT`):

```text
LBRACE  = Event(Indent, Increase)
RBRACE  = Event(Indent, Decrease)
KVSEP   = Literal(":")
ITEMSEP = Event(Line)
```

Under INDENT, additionally: only spaces are used for indentation; tabs are not permitted; the base indent unit is the greatest common divisor of all non-zero indentation widths, and every width is a multiple of it; each level change produces exactly one `Event(Indent, …)` token, so a jump of two levels yields two consecutive `LBRACE` tokens (§ Anonymous Maps).

Pragma directives may rebind individual tokens on top of a style (§ Pragma Directives). Any assignment satisfying the restrictions above is a legal surface, including one that mixes a literal block realizer with an event item realizer.

#### Occupied lexemes

A lexeme form occupied by the surface — a bound literal realizer, or one of the built-in literal keywords `true`, `false`, `null` — is no longer available as a bare key or bare value; quote it to use it as data (`` `and` ``, `"true"`). When a bound literal realizer coincides with a built-in literal form (`true`, `1`), that built-in form is shadowed in the document and must be quoted.

A surface that violates any restriction above raises an *Invalid Surface Error* before any parsing takes place.

### Reserved Words and Symbols

Beyond the four structural tokens, FlexConf reserves a fixed vocabulary of words and symbols. Whether an entry is reserved depends on **where** it appears, so the lists below are grouped by context rather than by spelling.

#### Fixed meta-syntax

These symbols are independent of the surface and can never be re-bound or shadowed by a literal realizer. A literal realizer must not contain `@` or `!`, and the `#` prefix rule applies in addition (§ Structural Tokens and Realizers):

| Symbol | Role | Defined in |
| --- | --- | --- |
| `#` | Introduces a comment that runs to the end of the line. | § Comments |
| `#?>` | Introduces a pragma directive; pragmas form a contiguous block at the head of a document. | § Pragma Directives |
| `@` | Introduces a date/time literal; outside strings, every `@` must begin a well-formed, calendar-valid date/time. | § Dates and Times |
| `!` | Reserved for future use. No production assigns it a meaning, so a bare `!` outside a string is a `SyntaxError`. | § Validity Rules |

#### Pragma vocabulary

The words below are reserved **only on a line that begins with `#?>`**. Anywhere else they are ordinary text, and may be used as bare keys or inside quoted values.

| Word | Position | Meaning |
| --- | --- | --- |
| `SET` | first word after `#?>` | Introduces a directive. |
| `STYLE` | after `SET` | Selects a named style preset. |
| `BRACE`, `INDENT` | after `STYLE` | Style names; case-sensitive. |
| `KVSEP`, `ITEMSEP`, `LBRACE`, `RBRACE` | after `SET` | Token names; case-sensitive. |
| `<INDENT>`, `<DEDENT>`, `<NEWLINE>` | value position | Event-realizer spellings. |

#### Literal keywords

These bare words carry a built-in type and are matched case-sensitively in their lower-case spellings — `TRUE` is not a boolean, it is a bare identifier.

| Word | Type |
| --- | --- |
| `true`, `false` | Boolean |
| `null` | Null |
| `inf`, `+inf`, `-inf`, `nan` | Special floats |

A bare word that is exactly `true`, `false`, or `null` is lexed as that keyword **in every position**, including before a `KVSEP`. Such a word therefore cannot be used as a bare key; write it as a quoted key (§ Keys) to use it as one. The special floats are recognized only in value position.

#### Delimiters with fixed roles

The characters `"`, `'`, and `` ` `` delimit strings and quoted keys, and `\` introduces an escape inside a basic (double-quoted) string. These roles are not configurable, and a literal realizer must not contain `"`, `'`, or `` ` `` (§ Structural Tokens and Realizers). The structural characters `:`, `,`, `{`, and `}` are reserved only while a realizer binds them to a token.

#### Lexical Boundaries

The reserved symbols above are lexically active at **both** ends of a token. Each of them can *open* a token — `'` and `"` open strings, `` ` `` opens a quoted key, `#` opens a comment (and `#?>` a pragma), `@` opens a date/time — and each of them **terminates a bare lexical run**: a bare identifier or numeric candidate stops at the first reserved symbol and never contains one.

A bare lexical run may therefore contain only the characters that § Keys allows for bare identifiers, together with the number grammar's characters (sign, fraction point, exponent marker, digit separators, and the `0x`/`0o`/`0b` radix prefixes). That character set is fixed: it does not depend on the effective surface. In particular `a'b`, `a"b`, `` a`b ``, `a#b`, `a@b`, and `a!b` are all invalid: the reserved symbol ends the run and then takes its own role (a quote opens a string, `#` starts a comment, `@` must introduce a well-formed date/time, `!` is a `SyntaxError`). Quote the text (`"a@b"`) to keep it as data.

**Matching order.** Tokenization resolves each position in four steps:

1. Every realizer that matches at the position is a candidate, as is the bare lexical run that begins there; reserved symbols take part in the same step with their fixed roles.
2. The **longest** candidate wins.
3. On a tie, a realizer wins over the bare run. Two realizers cannot tie, because the literal realizers of a document are pairwise distinct.
4. A winning bare run is then classified as a keyword, a number, or a bare identifier (§ Keys, § Values).

A literal realizer is therefore never matched inside a bare run — the run is longer there — while a realizer whose characters also occur inside bare runs still matches wherever a token boundary allows it. No rule separating the two character sets, and no rule forbidding a realizer to be a prefix of another, is needed.

This makes bare values a **closed set**. Outside a string, a bare value can only be:

- a Boolean — `true`, `false`
- Null — `null`
- a Number — an integer or float, including the special floats `inf`, `+inf`, `-inf`, `nan`
- a date/time literal introduced by `@`

Any other bare word in value position is a `SyntaxError`. A bare word is a key if and only if it is followed by a `KVSEP` (§ Keys); strings, which have no bare form, must always be quoted.

#### Usage Notes

- **`#` is always a comment.** Outside a string, everything from `#` to the end of the line is discarded, and a comment-only line produces no tokens. A `#` inside an unquoted key or value is never data; quote the text (`"a#b"`) to keep it.
- **`@` always begins a date/time.** A literal `@` — for example in an email address — must appear inside a quoted string (`"user@example.com"`). `@` is also forbidden in every literal parameter value.
- **`!` is reserved and currently has no meaning.** A bare `!` outside a string is a `SyntaxError`; quote it (`"a!b"`) to use it as data, and do not use it in a literal parameter value.
- **`#?>` is reserved, and pragmas are one contiguous block.** The pragma block is a contiguous run of `#?>` lines at the very start of the document, preceded only by whitespace, blank lines, and `#` comments. Outside a string value, a `#?>` line anywhere else — after the block, or after data has begun — is a `SyntaxError`, not a comment, so a misplaced directive is never silently ignored. Write `# ?>` when a comment is intended.
- **Bare words are not string values.** A value must be a string, a number, a boolean, null, or a date/time; `host: localhost` is invalid — write `host: "localhost"`.
- **A numeric-looking bare key is the literal string.** Per § Keys, `42:` yields the string key `"42"`. Implementations must preserve the source spelling of such a key; they must not normalize it through a numeric conversion.
- **A character with no role is a `SyntaxError`.** Outside a string, a character that matches no realizer and no reserved symbol — for instance a literal `{` in a document whose `LBRACE` is an event realizer — is a `SyntaxError` (§ Style Resolution and Surface Detection). Quote the text (`"{a}"`) to keep it, or bind the character as a realizer (§ Structural Tokens and Realizers).

### Comments

- Comments begin with `#` and continue to the end of the line.
- Comments may appear on their own line or after values on the same line.
- Comments are ignored by parsers; a comment-only line produces no tokens.
- The pragma prefix `#?>` is fixed meta-syntax, recognized before the surface takes effect (see § Pragma Directives).

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
- **Dates and Times**: bare literals introduced by the reserved sigil `@` (§ Dates and Times):
  - Offset date-time: `@1979-05-27T07:32:00Z`, `@1979-05-27T00:32:00.999-07:00`
  - Local date-time: `@1979-05-27T07:32:00`
  - Local date: `@1979-05-27`
  - Local time: `@07:32:00`

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

#### Dates and Times

Date and time values are bare literals introduced by the sigil `@`, using a profile of RFC 3339 / ISO 8601. Four forms exist:

```flexconf
odt1: @1979-05-27T07:32:00Z         # offset date-time (UTC)
odt2: @1979-05-27T00:32:00-07:00    # offset date-time (numeric offset)
odt3: @1979-05-27T00:32:00.999999Z  # fractional seconds
odt4: @1979-05-27 07:32:00Z         # space separator (one single space)
ldt:  @1979-05-27T07:32:00          # local date-time (no offset)
date: @1979-05-27                   # local date
time1: @07:32:00                    # local time
time2: @07:32:00.5                  # local time with fractional seconds
```

Rules:

- The `@` sigil is **fixed meta-syntax**, like the pragma prefix `#?>`: it never changes with the effective surface, and `@` must not appear in any literal realizer (§ Structural Tokens and Realizers).
- The date and time parts of a date-time are separated by `T`, `t`, or exactly one space character. The space form exists for readability (RFC 3339 §5.6); a space-separated date-time is one single lexical unit, and serializers must always emit the `T` form.
- The offset suffix is `Z`/`z` (UTC) or `±HH:MM`. Timezone database names are not used; a numeric offset is the only way to express zone information.
- Seconds range from `00` to `59`; leap seconds are not supported.
- Fractional seconds may carry any number of digits; implementations should support at least microsecond precision and may truncate beyond it.
- Values must denote calendar-valid dates and times: `@2026-02-30` or `@25:00:00` is a `SyntaxError`.
- A date/time literal must be followed by a structural delimiter (a separator, a comment, or whitespace) or by the end of input; e.g. `@2026-10-09x` is a `SyntaxError`.
- Outside string values, every `@` must introduce a well-formed date/time literal; any other use of `@` is a `SyntaxError`. In particular, a date/time literal is never a key.
- **Host mapping**: an offset date-time maps to a timezone-aware date-time type, a local date-time to a naive date-time type, a local date to a date type, and a local time to a time type.

### Block Structure

Every FlexConf document is built from a single abstract block rule, parameterized by the four structural tokens:

```text
block = LBRACE *(item ITEMSEP) [item] [ITEMSEP] RBRACE
item  = key KVSEP value    ; keyed item
      / value              ; anonymous item
```

- A block whose items are all **keyed** is a **Map**.
- A block whose items are all **anonymous** is an **Anonymous Map** (see below).
- Mixing keyed and anonymous items in the same block is invalid.
- A trailing `ITEMSEP` after the last item is permitted in the BRACE style.
- An empty block is an empty Map. It is expressible whenever `LBRACE` and `RBRACE` are literal realizers, and has no representation under `Event(Indent, …)` (§ Event realizers).

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

Note that in the INDENT style the block following a key is delimited by `Event(Indent, Increase)` / `Event(Indent, Decrease)` tokens and items are separated by `Event(Line)` tokens — the abstract block rule is unchanged.

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
- **Map items** are anonymous maps whose key-value pairs sit one indentation level deeper than the list level. This extra indentation level is required: it distinguishes the key-value pairs of a map item from the key-value pairs of the enclosing map. Consequently, when the first content line of an indented block is two indentation levels deeper than its key (two consecutive `LBRACE` tokens), the block is an anonymous map whose map items occupy the deeper level.
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

The effective surface of a document is resolved as follows:

1. **Pragma scanning**: The lexer scans the head of the file for pragma directives (§ Pragma Directives) and applies them in order of appearance. `SET STYLE <name>` binds the four tokens atomically; subsequent single-token `SET` directives rebind individual tokens.
2. **Surface selection**: After skipping whitespace and `#` comments, the first non-whitespace, non-comment character is examined:
   - If `LBRACE` is a literal realizer and the text at that position starts with it, the document uses the **explicit block surface**.
   - Otherwise the document uses the **indentation surface**, which requires `LBRACE = <INDENT>`; a document whose effective surface does not satisfy this is invalid.
   - A document with no pragma block has no declared surface; an implementation may infer one (§ Inferred Surfaces).
3. **Immutability**: Once selected, the surface cannot change within the document. A character that no realizer binds is not data: it is a `SyntaxError` when it occurs outside a string.

#### Inferred Surfaces

A document without a pragma block declares nothing about its surface, and its text may leave more than one surface consistent with it. An implementation may infer a surface under three requirements:

- **Candidates.** Inference considers, for every token, at least the two predefined styles and every literal realizer formed by a maximal punctuation run of the document.
- **Acceptance.** The inferred surface is usable only if every consistent surface yields the same data. When two consistent surfaces yield different data, the document is rejected with an error naming the token and the competing assignments — for example: *`,` is undetermined: `ITEMSEP = ','` reads `[1,2]`, `KVSEP = ','` reads `{"1":2}`; declare one with `#?>`.*
- **Diagnosis.** When no surface is consistent with the text, the error is reported in the terms of the surface that consumes the longest prefix of the document.

A document intended to be portable should carry a pragma block. Inference is a convenience: its result is not part of the language definition, and a document that parses under an inferred surface is not thereby guaranteed to parse under a different implementation's inference.

### Whitespace Handling

**General rule**: a whitespace character is syntactically significant if and only if the effective surface binds it to a syntactic role. Unbound whitespace is meaningless, and lexers skip it between tokens.

- In the default BRACE style all four tokens have literal realizers, so spaces, tabs, and newlines are all insignificant between tokens: documents may be reflowed and aligned freely.
- `ITEMSEP = <NEWLINE>` makes line endings significant (they *are* the separator), and two consecutive line endings form a blank line, which ends an anonymous map item in the INDENT style.
- `LBRACE = <INDENT>` / `RBRACE = <DEDENT>` make the leading whitespace of each line significant (it generates event tokens); whitespace within a line remains insignificant.
- Whitespace inside string values is always significant.
- Comments run from `#` to the end of the line; comment-only lines produce no tokens. A blank line produces an `ITEMSEP` token when `ITEMSEP = <NEWLINE>`.

### Conversions Between Styles

- Documents in any style can be converted to another style without loss of information, provided the target style can express the same data. An empty block is the case where it cannot: an empty block is expressible whenever `LBRACE` and `RBRACE` are literal realizers, and has no representation when they are `Event(Indent, …)` (§ Event realizers).
- The conversion must preserve all data and structure.
- Comments may be relocated but must be preserved.

### Pragma Directives

Pragmas start with `#?>` and rebind the structural tokens for the current file. The pragma prefix is fixed meta-syntax: it is always `#?>`, because pragmas are processed before the surface takes effect.

Pragmas form a single **pragma block**: a contiguous run of `#?>` lines at the very beginning of the document, preceded only by whitespace, blank lines, or `#` comments. No comment or blank line may appear between two pragma lines — the block ends at the first line that is not a pragma line. Outside a string value, a `#?>` line outside the block is a `SyntaxError`, not a comment. Two directive forms exist:

```flexconf
#?> SET STYLE INDENT           " named preset: binds the four tokens atomically
#?> SET STYLE BRACE            " the default style; may be omitted
#?> SET ITEMSEP ';'            " single-token override
#?> SET LBRACE '['
#?> SET RBRACE ']'
#?> SET LBRACE <INDENT>        " event realizers may also be set individually
```

Rules:

- Directives apply in order of appearance; later directives override earlier ones.
- The pragma block is contiguous: a comment or blank line between two directives ends it, and any later `#?>` line is a `SyntaxError`.
- A token value is either a quoted string (a literal realizer) or one of the event spellings `<INDENT>`, `<DEDENT>`, `<NEWLINE>`.
- `STYLE` accepts the style names `BRACE` and `INDENT` (case-sensitive).
- An unknown token name, unknown style name, or illegal value is a `SyntaxError`.
- All pragmas take effect before surface selection.

### Validity Rules

The following conditions make a FlexConf document invalid:

1. **Unbound structural character**: A character that no realizer binds, occurring outside a string (§ Lexical Boundaries).
2. **Invalid indentation** (INDENT style):
   - Using tabs for indentation
   - Non-uniform indentation levels (not multiples of the base indent unit)
3. **Mixed item forms in a block**: In a single block, items must either all have explicit keys or all be anonymous. Mixing is not permitted.
4. **Duplicate keys**: A map cannot contain duplicate keys at the same level.
5. **Incorrect item separation**:
   - In the INDENT style: missing blank lines between anonymous map items, or extra blank lines
   - In the BRACE style: missing `ITEMSEP` between items
6. **Unmatched braces**: Every `LBRACE` must have a matching `RBRACE`.
7. **Invalid surface**: A pragma or surface that violates the restrictions in § Structural Tokens and Realizers (unknown token names, duplicate literal realizers, an event realizer bound to the wrong token, ...).
8. **Invalid date/time literal or reserved symbol**: an `@` outside a string that does not introduce a well-formed, calendar-valid date/time literal, or a bare `!` outside a string (§ Dates and Times, § Reserved Words and Symbols).
9. **Misplaced pragma**: a `#?>` line that is not part of the contiguous pragma block at the beginning of the document (§ Pragma Directives).

### Filename Extension

- FlexConf files should use the extension `.fc`.

### MIME Type

- The MIME type for FlexConf files is `application/flexconf`.

## Formal Grammar

A formal ABNF grammar for FlexConf is available in [FlexConf ABNF Grammar SPEC](./FlexConf%20ABNF%20Grammar%20SPEC.md).

---

Copyright © 2025 FlexConf Foundation. All rights reserved.
This specification is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.
