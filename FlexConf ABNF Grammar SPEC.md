# FlexConf ABNF Grammar Specification

*Version 0.0.1-snapshot*
*Published on November 24, 2025*

## Introduction

This document provides the formal ABNF (Augmented Backus-Naur Form) grammar for the FlexConf 1.0 specification. The grammar defines the syntax rules for valid FlexConf documents in both indentation mode and bracket mode.
Although this design has basically taken shape, there are still some details under consideration and it will continue to evolve until it is finally finalized.

## Core Definitions

```abnf
; Basic character classes
DIGIT       = %x30-39                ; 0-9
ALPHA       = %x41-5A / %x61-7A     ; A-Z / a-z
HEXDIG      = DIGIT / "A" / "B" / "C" / "D" / "E" / "F" /
              "a" / "b" / "c" / "d" / "e" / "f"
UNDERSCORE  = "_"
HYPHEN      = "-"
DOT         = "."
SP          = %x20                   ; space
HTAB        = %x09                   ; horizontal tab
LF          = %x0A                   ; linefeed
CR          = %x0D                   ; carriage return
CRLF        = CR LF
NEWLINE     = LF / CRLF
WS          = SP / HTAB              ; whitespace
WSP         = *(WS / NEWLINE)        ; optional whitespace
```

## Document Structure

```abnf
flexconf-doc = (indentation-mode / bracket-mode)

; Syntax mode detection
indentation-mode = *comment *(indentation-key-value-pair / indentation-list / indentation-map)
bracket-mode = %x7B WSP bracket-document-content WSP %x7D  ; {
```

## Common Elements

```abnf
comment = "#" *(%x01-09 / %x0B-0C / %x0E-10FFFF) NEWLINE

key = bare-key / quoted-key
bare-key = (ALPHA / "_") *(ALPHA / DIGIT / UNDERSCORE / HYPHEN / DOT)
quoted-key = "`" quoted-key-content "`"
quoted-key-content = *(%x01-5F / %x61-10FFFF)  ; Any Unicode char except backtick

indentation-key-value-pair = key WSP ":" WSP indentation-value [WSP comment] NEWLINE

primitive = string / number / boolean / null

indentation-value = primitive / indentation-map / indentation-list
bracket-value = primitive / bracket-map / bracket-list

string = basic-string / ml-basic-string / literal-string / ml-literal-string
number = integer / float / hex-int / oct-int / bin-int
boolean = "true" / "false"
null = "null"
```

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
ml-basic-char = *(%x01-09 / %x0B-0C / %x0E-21 / %x23-10FFFF) / escape-sequence

literal-string = %x27 *literal-char %x27  ; '
literal-char = %x09 / %x20-26 / %x28-10FFFF  ; Tab and any char except '

ml-literal-string = %x27.27.27 *ml-literal-char %x27.27.27  ; '''
ml-literal-char = *(%x01-09 / %x0B-0C / %x0E-26 / %x28-10FFFF)  ; Any char except '
```

## Numeric Types

```abnf
integer = [sign] dec-int
float = [sign] ((dec-int frac) / (dec-int frac exp) / (dec-int exp))
sign = "+" / "-"
dec-int = "0" / (nonzero-digit *("_" DIGIT))
nonzero-digit = %x31-39  ; 1-9
frac = "." 1*DIGIT
exp = ("e" / "E") [sign] 1*DIGIT

hex-int = "0" ("x" / "X") hex-prefix *(("_" hex-value) / hex-value)
hex-prefix = HEXDIG
hex-value = 1*HEXDIG

oct-int = "0" ("o" / "O") oct-prefix *(("_" oct-value) / oct-value)
oct-prefix = %x30-37  ; 0-7
oct-value = 1*(%x30-37)  ; 0-7

bin-int = "0" ("b" / "B") bin-prefix *(("_" bin-value) / bin-value)
bin-prefix = %x30-31  ; 0-1
bin-value = 1*(%x30-31)  ; 0-1

special-float = ("+" / "-") "inf" / "nan"
```

## Collections

```abnf
; Indentation mode structures
indentation-map = *indentation-key-value-pair
indentation-list = indentation-list-item *(NEWLINE indentation-list-item)
indentation-list-item = indentation-value

; Bracket mode structures
bracket-container = %x7B WSP (bracket-map-content / bracket-list-content) WSP %x7D

bracket-map-content = *([bracket-map-member] WSP ",") [bracket-map-member]
bracket-map-member = key WSP ":" WSP bracket-value

bracket-list-content = *([bracket-list-item] WSP ",") [bracket-list-item]
bracket-list-item = bracket-value

bracket-value = primitive / bracket-container
```

## Document Content

```abnf
bracket-document-content = bracket-map-content
```

## Validity Constraints

The following constraints are not directly expressible in ABNF but must be enforced:

1. **Indentation Mode Constraints**:
   - Tabs must not be used for indentation
   - Indentation levels must be consistent multiples of the base indent unit
   - New line must separate all items in maps and lists.

2. **Bracket Mode Constraints**:
   - All braces must be properly matched and nested
   - Commas must separate all items in maps and lists (except the last item, where a trailing comma is optional)

3. **General Constraints**:
   - Keys in the same map must be unique
   - A document must use exclusively one syntax mode
   - UTF-8 encoding must be valid
   - Control characters (except tab, LF, and CR) must not appear outside of string values

## Example Document Parsing

### Indentation Mode Example

```flexconf
server:
    host: "localhost"
    port: 8080

    host: "production.example.com"
    port: 443
```

This would be parsed according to the `indentation-mode` rules, with host and port at same indent level create a nested maps, and nested maps separated by new line.

### Bracket Mode Example

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

This would be parsed according to the `bracket-mode` rules, with the double-braced `{{...}}` denoting a list.

---

Copyright © 2025 Hypnoes Liu. All rights reserved.
This specification is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License.
