# FlexConf ABNF Grammar Specification

*Version 0.0.3-snapshot*
*Published on November 24, 2025; revised on October 12, 2026*

## Introduction

This document provides the formal ABNF (Augmented Backus-Naur Form) grammar for the FlexConf 1.0 specification.

FlexConf has a single unified structural grammar whose surface terminals are **configurable** (see the Language Specification, § Structural Tokens and Realizers). The ABNF rules below are written against parameterized terminals (`lbrace`, `rbrace`, `kv-sep`, `item-sep`), each of which realizes one of the four structural tokens: `lbrace` realizes `LBRACE`, `rbrace` realizes `RBRACE`, `kv-sep` realizes `KVSEP`, and `item-sep` realizes `ITEMSEP`. The rules give the **default instantiation** — the BRACE style. Bindings for other surfaces, including the event realizers of the INDENT style, are given in notes and in § Validity Constraints, since line-structure analysis cannot be expressed in ABNF. The comment terminal `comment-mark` has the single instantiation `"#"`.

## Tokens and Terminals

| Token | ABNF terminal | Default instantiation (BRACE) | INDENT style binding |
| --- | --- | --- | --- |
| `KVSEP` | `kv-sep` | `":"` | `":"` |
| `ITEMSEP` | `item-sep` | `","` | `<NEWLINE>` (event) |
| `LBRACE` | `lbrace` | `%x7B` (`{`) | `<INDENT>` (event) |
| `RBRACE` | `rbrace` | `%x7D` (`}`) | `<DEDENT>` (event) |

```abnf
; Default instantiation of the parameterized terminals
kv-sep        = ":"
item-sep      = ","
lbrace        = %x7B          ; {
rbrace        = %x7D          ; }

; The comment marker
comment-mark  = "#"
```

The event spellings `<INDENT>`, `<DEDENT>`, and `<NEWLINE>` realize a terminal from line-structure analysis rather than from a written string. When `item-sep` is `<NEWLINE>`, every line ending produces one `item-sep` token, so a blank line produces two consecutive `item-sep` tokens (this ends an anonymous map item, see the Language Specification).

**Matching order** is not expressible in ABNF and is fixed by the Language Specification: at each position the candidates are every matching terminal and the bare lexical run beginning there; the longest candidate wins, and on a tie a parameterized terminal wins over the bare lexical run. A literal terminal is therefore never matched inside a bare lexical run, and one terminal may be a prefix of another without ambiguity.

## Reserved Tokens

In addition to the parameterized terminals, FlexConf has a fixed vocabulary that no configuration can re-bind. The terminals below are *fixed meta-syntax*, independent of `kv-sep`, `item-sep`, `lbrace`, and `rbrace`:

| Terminal | Instantiation | Constraints |
| --- | --- | --- |
| `comment-mark` | `"#"` | No literal realizer may equal `"#"` or share a prefix with it. |
| pragma prefix | `"#?>"` | Part of a contiguous pragma block at the head of the document, before surface selection; outside a string, a `#?>` line outside that block is a syntax error, not a comment. |
| date/time sigil | `"@"` | No literal realizer may contain it; outside strings, every `@` must open a well-formed `date-time`. |
| reserved sigil | `"!"` | Reserved for future use and given no production; no literal realizer may contain it, and a bare `!` outside a string is a syntax error. |

The pragma prefix, the date/time sigil, and the reserved `!` are not ABNF rules of the parameterized grammar; they are consumed by the lexer before and around it, which is what makes them fixed. The reserved symbols are **lexically active at both ends of a token**: the string delimiters, `` ` ``, `comment-mark`, `@`, and `!` all terminate a bare lexical run, so none of them can be absorbed into an identifier (`a'b`, `a@b`, `a!b`, and so on are syntax errors). The pragma vocabulary itself (`SET`, `STYLE`, `BRACE`, `INDENT`, `KVSEP`, `ITEMSEP`, `LBRACE`, `RBRACE`, `<INDENT>`, `<DEDENT>`, `<NEWLINE>`) is reserved **only** inside a `pragma-line`; elsewhere those words are ordinary `bare-key`s.

Bare literals with a built-in type are reserved words rather than identifiers:

| Word | Production | Reserved status |
| --- | --- | --- |
| `true`, `false` | `boolean` | Never an `IDENTIFIER`; cannot be used as a bare key. |
| `null` | `null` | Never an `IDENTIFIER`; cannot be used as a bare key. |
| `inf`, `nan` (optionally signed) | `special-float` | Value position only; not special as a bare key. |

For a bare lexical run that is exactly `true`, `false`, or `null`, the `boolean` / `null` production takes precedence over `bare-key`, so a `key` written this way must use `quoted-key` (or a `string`) instead. This is the keyword counterpart of the rule in § Validity Constraints that a run matching both `number` and `bare-key` is a key if and only if it is followed by `kv-sep`.

ABNF treats quoted-string terminals as case-insensitive by default; for FlexConf the keyword literals, the style names `BRACE` / `INDENT`, and the pragma token names are matched **case-sensitively** in their listed spellings. The grammar should be read as if these terminals used `%s` string notation, so `TRUE`, `True`, `indent`, and `itemsep` do not match.

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

**Whitespace rule (parameterized)**: whitespace that is not bound to a syntactic role by the effective surface is insignificant and skipped between tokens. In the default instantiation:

```abnf
WSP         = *(WS / NEWLINE)        ; BRACE style: all whitespace skippable
```

When `item-sep` is bound to `<NEWLINE>`, line endings are significant and must be excluded: `WSP = *WS`. When `lbrace` is bound to `<INDENT>`, the leading whitespace of each line is additionally significant (it generates event tokens) and is excluded from `WSP` at line start.

## Document Structure

```abnf
flexconf-document = [pragma-section] (explicit-document / implicit-document)

; A document with physical braces (BRACE style, or any literal lbrace)
explicit-document = block

; A document whose root block has no enclosing braces (INDENT style:
; the root block's virtual lbrace/rbrace are the start and end of the
; document, and every item-sep below is a virtual <NEWLINE> token)
implicit-document = block-content

; Pragma directives (fixed "#?>" meta-syntax, independent of comment-mark).
; The pragma block is a contiguous run of pragma lines at the very start of
; the document; only whitespace, blank lines, and comment lines may precede
; it. A "#?>" line that is not part of this block is a syntax error, so the
; generic comment production below does not cover it.
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

**Event-realizer specializations** (not expressible in pure ABNF):

- `lbrace` / `rbrace` are the `<INDENT>` / `<DEDENT>` events; `item-sep` is `<NEWLINE>`.
- Two consecutive `<INDENT>` events open an anonymous map whose map items sit one indentation level deeper than its scalar items — the block opens with two consecutive `LBRACE` tokens.
- Two consecutive `item-sep` tokens (a blank line) end the current anonymous map item.
- An anonymous map of maps opens with two consecutive `LBRACE` tokens in every surface: with literal `lbrace` / `rbrace` it is written as double braces (`{{ … }}`), with the INDENT events as a double indent.

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

offset-date-time = full-date ("T" / "t" / SP) full-time
local-date-time  = full-date ("T" / "t" / SP) partial-time
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

The date/time literal is a single lexical unit: the `@` sigil and the entire date/time body are consumed atomically, so the `:` characters inside `partial-time` never interact with `kv-sep`. The SP separator in `offset-date-time` / `local-date-time` is exactly one space character. The body must be followed by a delimiter or the end of input (see § Validity Constraints).

## Validity Constraints

The following constraints are not directly expressible in ABNF but must be enforced:

1. **Realizer Constraints**:
   - The literal realizers of a document are pairwise distinct, and none equals `comment-mark` (`"#"`) or shares a prefix with it.
   - No literal realizer may contain `@` (reserved for date/time literals) or `!` (reserved for future use).
   - `<INDENT>` / `<DEDENT>` are bound as a pair to `lbrace` / `rbrace`, and no other event spelling is bound to those terminals.

2. **Surface Constraints**:
   - A document uses exactly one surface.
   - A character consumed by no token — by no realizer, by no reserved symbol, and not as part of a bare lexical run — is a syntax error outside string values.
   - In an explicit surface, all braces must be properly matched and nested.

3. **INDENT Style (Virtual Token) Constraints**:
   - Tabs must not be used for indentation.
   - Indentation levels must be consistent multiples of the base indent unit (the GCD of all non-zero indentation widths).
   - Every line ending produces one `item-sep` token; adjacent anonymous map items are separated by exactly one blank line (two consecutive `item-sep` tokens).

4. **General Constraints**:
   - Keys in the same map must be unique.
   - A single block must not mix keyed and anonymous items.
   - A lexical run matching both `number` and `bare-key` (e.g. `42`) is a **key** if and only if it is followed (after optional whitespace) by `kv-sep`; its key value is the literal string.
   - A `date-time` literal must denote a calendar-valid date and time (`2026-02-30`, `25:00:00`, etc. are invalid) and must be followed by a delimiter (whitespace, a separator, or `comment-mark`) or the end of input. Outside strings, every `@` must begin a well-formed `date-time`; any other `@` is a syntax error.
   - Outside a string, a `#?>` line outside the contiguous head pragma block is a syntax error, not a comment.
   - Outside strings a bare `!` is a syntax error. No reserved symbol (`'`, `"`, `` ` ``, `#`, `@`, `!`) may be absorbed into a `bare-key` or any other bare lexical run; each terminates the run and then takes its own role. A bare value is therefore restricted to `boolean`, `null`, `number` (including `special-float`), and `date-time`; every other bare word in value position is a syntax error.
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
