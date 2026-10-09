# FlexConf ABNF Grammar Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 8, 2026*

## Introduction

This document provides the formal ABNF (Augmented Backus-Naur Form) grammar for the FlexConf 1.0 specification.

FlexConf has a single unified structural grammar whose surface terminals are **configurable** (see the Language Specification, § Syntax Parameters). The ABNF rules below are written against parameterized terminals (`lbrace`, `rbrace`, `kv-sep`, `item-sep`) and give the **default instantiation** — the BRACE style. Bindings for other styles, including the virtual tokens of the INDENT style, are given in notes and in § Validity Constraints, since indentation analysis cannot be expressed in ABNF. The comment terminal `comment-mark` has the single instantiation `"#"`. The date/time sigil `@` is likewise fixed meta-syntax, independent of all parameters.

## Syntax Parameters and Terminals

| Parameter | ABNF terminal | Default instantiation (BRACE) | INDENT style binding |
| --- | --- | --- | --- |
| `KeyValueSeparator` | `kv-sep` | `":"` | `":"` |
| `ItemSeparator` | `item-sep` | `","` | `<NEWLINE>` (virtual) |
| `LeftBrace` | `lbrace` | `%x7B` (`{`) | `<INDENT>` (virtual) |
| `RightBrace` | `rbrace` | `%x7D` (`}`) | `<DEDENT>` (virtual) |

```abnf
; Default instantiation of the parameterized terminals
kv-sep        = ":"
item-sep      = ","
lbrace        = %x7B          ; {
rbrace        = %x7D          ; }

; The comment marker
comment-mark  = "#"
```

Symbolic values `<INDENT>`, `<DEDENT>`, and `<NEWLINE>` denote virtual tokens generated from line-structure analysis. When `item-sep` is bound to `<NEWLINE>`, every line ending produces one `item-sep` token, so a blank line produces two consecutive `item-sep` tokens (this ends an anonymous map item, see the Language Specification).

## Core Definitions

```abnf
; Basic character classes
DIGIT       = %x30-39                ; 0-9
ALPHA       = %x41-5A / %x61-7A     ; A-Z / a-z
HEXDIG      = DIGIT / "A" / "B" / "C" / "D" / "E" / "F" /
              "a" / "b" / "c" / "d" / "e" / "f"
UNDERSCORE  = "_"
HYPHEN      = "-"
SP          = %x20                   ; space
HTAB        = %x09                   ; horizontal tab
LF          = %x0A                   ; linefeed
CR          = %x0D                   ; carriage return
CRLF        = CR LF
NEWLINE     = LF / CRLF
WS          = SP / HTAB              ; inline whitespace
```

**Whitespace rule (parameterized)**: whitespace that is not bound to a syntactic role by the effective configuration is insignificant and skipped between tokens. In the default instantiation:

```abnf
WSP         = *(WS / NEWLINE)        ; BRACE style: all whitespace skippable
```

When `item-sep` is bound to `<NEWLINE>`, line endings are significant and must be excluded: `WSP = *WS`. When `lbrace` is bound to `<INDENT>`, the leading whitespace of each line is additionally significant (it generates virtual tokens) and is excluded from `WSP` at line start.

## Document Structure

```abnf
flexconf-document = [pragma-section] (explicit-document / implicit-document)

; A document with physical braces (BRACE style, or any literal lbrace)
explicit-document = block

; A document whose root block has no enclosing braces (INDENT style:
; the root block's virtual lbrace/rbrace are the start and end of the
; document, and every item-sep below is a virtual <NEWLINE> token)
implicit-document = block-content

; Pragma directives (fixed "#?>" meta-syntax, independent of comment-mark)
pragma-section = 1*(pragma-line NEWLINE)
pragma-line    = "#?>" *(%x01-09 / %x0B-0C / %x0E-10FFFF)
```

## Common Elements

```abnf
comment = comment-mark *(%x01-09 / %x0B-0C / %x0E-10FFFF) NEWLINE

key = bare-key / quoted-key
bare-key = 1*(ALPHA / DIGIT / UNDERSCORE / HYPHEN)
quoted-key = "`" quoted-key-content "`"
quoted-key-content = *(%x01-5F / %x61-10FFFF)  ; Any Unicode char except backtick

value = primitive / block

primitive = string / number / boolean / null / date-time

string = basic-string / ml-basic-string / literal-string / ml-literal-string
number = integer / float
boolean = "true" / "false"
null = "null"
```

## Block Structure

The single abstract block rule, shared by every style:

```abnf
block = lbrace WSP block-content WSP rbrace

block-content = *(item WSP item-sep WSP) [item [WSP item-sep]]

item = keyed-item / anonymous-item
keyed-item    = key WSP kv-sep WSP value
anonymous-item = value
```

- A `block` whose items are all `keyed-item` is a **map**.
- A `block` whose items are all `anonymous-item` is an **anonymous map** (a list); its implicit keys are the strings `"0"`, `"1"`, `"2"`, ... assigned in order of appearance.
- Mixing `keyed-item` and `anonymous-item` in one block is invalid (see § Validity Constraints).
- The trailing `item-sep` is optional (permitted in the BRACE style).

**INDENT style specializations** (virtual-token instantiation, not expressible in pure ABNF):

- `lbrace` / `rbrace` are `<INDENT>` / `<DEDENT>` tokens; `item-sep` is `<NEWLINE>`.
- Two consecutive `<INDENT>` tokens open an anonymous map whose map items sit one indentation level deeper than its scalar items.
- Two consecutive `item-sep` tokens (a blank line) end the current anonymous map item.
- In the BRACE style, an anonymous map of maps appears as double braces: the outer `lbrace` opens the anonymous map, each inner `block` is one map item.

## String Types

```abnf
basic-string = %x22 *basic-char %x22  ; "
basic-char = %x20-21 / %x23-5B / %x5D-10FFFF / escape-sequence

escape-sequence = "\" (
    %x22 /   ; "    quotation mark
    %x5C /   ; \    reverse solidus
    %x62 /   ; b    backspace
    %x66 /   ; f    form feed
    %x6E /   ; n    linefeed
    %x72 /   ; r    carriage return
    %x74 /   ; t    tab
    %x75 4HEXDIG /  ; uXXXX
    %x55 8HEXDIG    ; UXXXXXXXX
)

ml-basic-string = %x22.22.22 *ml-basic-char %x22.22.22  ; """
ml-basic-char = %x01-21 / %x23-10FFFF / escape-sequence
               ; Any char except unescaped '"'; newlines allowed (%x0A included)

literal-string = %x27 *literal-char %x27  ; '
literal-char = %x09 / %x20-26 / %x28-10FFFF  ; Tab and any char except '

ml-literal-string = %x27.27.27 *ml-literal-char %x27.27.27  ; '''
ml-literal-char = %x01-26 / %x28-10FFFF  ; Any char except '
```

## Numeric Types

```abnf
integer = [sign] dec-int / hex-int / oct-int / bin-int
float   = [sign] (dec-int frac [exp] / dec-int exp / special-float)
special-float = "inf" / "nan"

sign = "+" / "-"

dec-int = "0" / nonzero-digit *DIGIT *(UNDERSCORE 1*DIGIT)
nonzero-digit = %x31-39  ; 1-9
frac = "." 1*DIGIT
exp = ("e" / "E") [sign] 1*DIGIT

hex-int = "0" ("x" / "X") 1*HEXDIG *(UNDERSCORE 1*HEXDIG)
oct-int = "0" ("o" / "O") 1*(%x30-37) *(UNDERSCORE 1*(%x30-37))
bin-int = "0" ("b" / "B") 1*(%x30-31) *(UNDERSCORE 1*(%x30-31))
```

## Date and Time Types

A profile of RFC 3339 / ISO 8601, introduced by the fixed sigil `@` (not a syntax parameter):

```abnf
date-time = "@" (offset-date-time / local-date-time / local-date / local-time)

offset-date-time = full-date ("T" / "t") full-time
local-date-time  = full-date ("T" / "t") partial-time
local-date       = full-date
local-time       = partial-time

full-date      = date-fullyear "-" date-month "-" date-mday
date-fullyear  = 4DIGIT
date-month     = 2DIGIT        ; 01-12
date-mday      = 2DIGIT        ; 01-31, bounded by month and year
partial-time   = time-hour ":" time-minute ":" time-second [time-secfrac]
full-time      = partial-time time-offset
time-hour      = 2DIGIT        ; 00-23
time-minute    = 2DIGIT        ; 00-59
time-second    = 2DIGIT        ; 00-59 (leap seconds are not supported)
time-secfrac   = "." 1*DIGIT
time-offset    = ("Z" / "z") / time-numoffset
time-numoffset = ("+" / "-") time-hour ":" time-minute
```

The date/time literal is a single lexical unit: the `@` sigil and the entire date/time body are consumed atomically, so the `:` characters inside `partial-time` never interact with `kv-sep`. The body must be followed by a delimiter or the end of input (see § Validity Constraints).

## Validity Constraints

The following constraints are not directly expressible in ABNF but must be enforced:

1. **Configuration Constraints**:
   - The literal values of the four structural parameters are pairwise distinct and conflict-free with `comment-mark` (`"#"`).
   - No literal parameter value may contain `@` (reserved for date/time literals).
   - `<INDENT>` / `<DEDENT>` are bound as a pair to `lbrace` / `rbrace`.

2. **Style and Surface Constraints**:
   - A document uses exactly one surface style; literal braces must not appear in the indentation surface (outside strings).
   - In the explicit surface, all braces must be properly matched and nested.

3. **INDENT Style (Virtual Token) Constraints**:
   - Tabs must not be used for indentation.
   - Indentation levels must be consistent multiples of the base indent unit (the GCD of all non-zero indentation widths).
   - Every line ending produces one `item-sep` token; adjacent anonymous map items are separated by exactly one blank line (two consecutive `item-sep` tokens).

4. **General Constraints**:
   - Keys in the same map must be unique.
   - A single block must not mix keyed and anonymous items.
   - A lexical run matching both `number` and `bare-key` (e.g. `42`) is a **key** if and only if it is followed (after optional whitespace) by `kv-sep`; its key value is the literal string.
   - A `date-time` literal must denote a calendar-valid date and time (`2026-02-30`, `25:00:00`, etc. are invalid) and must be followed by a delimiter (whitespace, a separator, or `comment-mark`) or the end of input. Outside strings, every `@` must begin a well-formed `date-time`; any other `@` is a syntax error.
   - UTF-8 encoding must be valid.
   - Control characters (except tab, LF, and CR) must not appear outside of string values.

## Example Document Parsing

### INDENT Style Example

```flexconf
server:
    host: "localhost"
    port: 8080

    host: "production.example.com"
    port: 443
```

This is parsed with the INDENT bindings: each deeper indentation level generates a virtual `lbrace`, the two consecutive `lbrace` tokens after `server:` open an anonymous map whose map items sit at the deeper level, and the blank line (two consecutive virtual `item-sep` tokens) ends the first map item.

### BRACE Style Example

```flexconf
{
  server: {{
    host: "localhost",
    port: 8080
  }, {
    host: "production.example.com",
    port: 443
  }}
}
```

This is parsed with the default instantiation, the double-braced `{{...}}` denoting an anonymous map of maps.

---

Copyright © 2025 FlexConf Foundation. All rights reserved.
This specification is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.
