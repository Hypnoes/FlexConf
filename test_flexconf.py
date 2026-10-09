import sys
sys.path.insert(0, r"D:\workspaces\GitHub.com\flex-conf")
import flexconf

passed = failed = 0

def check(name, text, expected=None, expect_error=None, config=None):
    global passed, failed
    try:
        result = flexconf.loads(text, config=config)
        if expect_error:
            print(f"FAIL  {name}: expected error {expect_error}, got {result!r}")
            failed += 1
        elif expected is not None and result != expected:
            print(f"FAIL  {name}:\n  expected {expected!r}\n  got      {result!r}")
            failed += 1
        else:
            print(f"PASS  {name}: {result!r}")
            passed += 1
    except Exception as e:
        if expect_error and expect_error in str(e):
            print(f"PASS  {name}: raised {e}")
            passed += 1
        else:
            print(f"FAIL  {name}: unexpected {type(e).__name__}: {e}")
            failed += 1

# 1. Language SPEC list example (maps + scalars)
check("SPEC list example (L177)", '''protocols:
    name: "http"
    port: 8080

    name: "https"
    port: 443
  9000
  "10010-10015"
''', expected={'protocols': [
    {'name': 'http', 'port': 8080},
    {'name': 'https', 'port': 443},
    9000, '10010-10015']})

# 2. Mixed collections example: servers must be a list of TWO maps
check("SPEC mixed collections (L225)", '''application:
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
''', expected={'application': {
    'name': 'DataProcessor', 'version': '1.0',
    'servers': [{'host': 'localhost', 'port': 8080},
                {'host': 'production.example.com', 'port': 443}],
    'settings': {'debug': True, 'timeout': 30}}})

# 3. Simple nested map (L152)
check("SPEC nested map (L152)", '''server:
  host: "localhost"
  port: 8080
  ssl: false
''', expected={'server': {'host': 'localhost', 'port': 8080, 'ssl': False}})

# 4. Numeric-key conceptual form (L191)
check("SPEC numeric keys (L191)", '''protocols:
  0:
    name: "http"
    port: 8080
  1:
    name: "https"
    port: 443
  2: 9000
  3: "10010-10015"
''', expected={'protocols': {
    '0': {'name': 'http', 'port': 8080},
    '1': {'name': 'https', 'port': 443},
    '2': 9000, '3': '10010-10015'}})

# 5. Duplicate keys must raise (Validity Rule 4)
check("duplicate key error", "a: 1\na: 2\n", expect_error="Duplicate key 'a'")

# 6. Blank line inside a plain map is tolerated, no split
check("blank line in plain map", '''server:
  host: "a"
  port: 1

  admin: true
''', expected={'server': {'host': 'a', 'port': 1, 'admin': True}})

# 7. Comment between list maps does NOT separate (still one map -> duplicate)
check("comment is not a separator", '''items:
    name: "a"
    # just a comment
    name: "b"
''', expect_error="Duplicate key 'name'")

# 8. Pure scalar list regression
check("scalar list", "list_example:\n    1\n    2\n    3\n",
      expected={'list_example': [1, 2, 3]})

# 9. Bracket mode regression
check("bracket map", '{\n  server: {\n    host: "localhost",\n    port: 8080\n  }\n}\n',
      expected={'server': {'host': 'localhost', 'port': 8080}})
check("bracket list of maps", '{\n  p: {\n    { name: "http", port: 8080 },\n    9000\n  }\n}\n',
      expected={'p': [{'name': 'http', 'port': 8080}, 9000]})

# 10. Deeply nested anonymous map (value inside anonymous map)
check("nested value in anonymous map", '''servers:
    host: "a"
    limits:
      cpu: 2

    host: "b"
''', expected={'servers': [
    {'host': 'a', 'limits': {'cpu': 2}},
    {'host': 'b'}]})

# 11. AST layer: parse() returns IR nodes (Parser SPEC 2)
def check_true(name, cond, detail=""):
    global passed, failed
    if cond:
        print(f"PASS  {name}")
        passed += 1
    else:
        print(f"FAIL  {name}: {detail}")
        failed += 1

ast = flexconf.parse('''protocols:
    name: "http"
    port: 8080

    name: "https"
    port: 443
  9000
  "10010-10015"
''')
check_true("parse() root is MapNode", isinstance(ast, flexconf.MapNode),
           type(ast).__name__)
proto = ast.entries.get('protocols') if isinstance(ast, flexconf.MapNode) else None
check_true("protocols is ListNode", isinstance(proto, flexconf.ListNode),
           type(proto).__name__)
kinds = [type(e).__name__ for e in proto.elements] if isinstance(proto, flexconf.ListNode) else []
check_true("list = 2 anonymous MapNodes + 2 ScalarNodes",
           kinds == ['MapNode', 'MapNode', 'ScalarNode', 'ScalarNode'], str(kinds))

# 12. AST nodes carry line/col info
ast2 = flexconf.parse('server:\n  host: "a"\n  port: 1\n')
host = ast2.entries['server'].entries['host']
check_true("ScalarNode keeps value and line",
           isinstance(host, flexconf.ScalarNode) and host.value == 'a' and host.line == 2,
           f"{host!r}")

# 13. Interpreter maps AST to native types (Parser SPEC 5.1)
native = flexconf.Interpreter().to_native(flexconf.parse('server:\n  host: "localhost"\n  port: 8080\n'))
check_true("interpreter over parse() output",
           native == {'server': {'host': 'localhost', 'port': 8080}},
           repr(native))

# 14. SET STYLE INDENT: explicitly declared indentation surface parses
#     identically to the auto-detected default
check("pragma SET STYLE INDENT", '''#?> SET STYLE INDENT
server:
  host: "localhost"
  port: 8080
''', expected={'server': {'host': 'localhost', 'port': 8080}})

# 15. Custom ItemSeparator ';' in the BRACE style, with free multi-line
#     layout (whitespace is insignificant unless bound, Language SPEC)
check("pragma ItemSeparator ';'", '''#?> SET ItemSeparator ';'
{
  a: 1;
  b: {
    x: true;
    y: 2;
  };
}
''', expected={'a': 1, 'b': {'x': True, 'y': 2}})

# 16. Custom LeftBrace/RightBrace '[' ']' + surface detection on '['
check("pragma LeftBrace '[' RightBrace ']'", '''#?> SET LeftBrace '['
#?> SET RightBrace ']'
[ a: 1, b: [ 1, 2 ] ]
''', expected={'a': 1, 'b': [1, 2]})

# 17. API-level config: KeyValueSeparator '=' in the explicit surface
check("API Config(key_value_separator='=')",
      "{a = 1}", config=flexconf.Config(key_value_separator='='),
      expected={'a': 1})

# 17b. API-level config on the indentation surface (style_indent override)
check("API style_indent(key_value_separator='=')",
      "a = 1\n", config=flexconf.Config.style_indent(key_value_separator='='),
      expected={'a': 1})

# 18. Comments start with '#'
check("CommentMarker pragma rejected",
      "#?> SET CommentMarker '//'\n{}\n",
      expect_error="Unknown pragma parameter 'CommentMarker'")
check("'//' is not a comment", "{ a: 1 // oops\n}\n",
      expect_error="Expected COLON")

# 19. Invalid configurations and pragmas are rejected
def check_raises(name, fn, expect_error):
    global passed, failed
    try:
        fn()
        print(f"FAIL  {name}: expected error {expect_error}, no error raised")
        failed += 1
    except Exception as e:
        if expect_error in str(e):
            print(f"PASS  {name}: raised {e}")
            passed += 1
        else:
            print(f"FAIL  {name}: unexpected {type(e).__name__}: {e}")
            failed += 1

check_raises("Config conflict: ItemSeparator ':' vs KeyValueSeparator ':'",
             lambda: flexconf.Config(item_separator=':'),
             "Invalid configuration")
check_raises("Config conflict: unpaired <INDENT>",
             lambda: flexconf.Config(left_brace=flexconf.INDENT),
             "Invalid configuration")
check_raises("Config conflict: ItemSeparator conflicts with the comment marker",
             lambda: flexconf.Config(item_separator='#'),
             "Invalid configuration")
check("unknown style name rejected", "#?> SET STYLE YAML\n{}\n",
      expect_error="Unknown style 'YAML'")
check("indent doc rejected when pragmas declare literal braces",
      "#?> SET ItemSeparator ';'\nserver:\n  a: 1\n",
      expect_error="SET STYLE INDENT")

# 20. Date/time literals: '@' sigil, RFC 3339 profile (Language SPEC:
#     Dates and Times)
from datetime import date, datetime, time, timedelta, timezone

check("offset date-time Z", "x: @1979-05-27T07:32:00Z\n",
      expected={'x': datetime(1979, 5, 27, 7, 32, tzinfo=timezone.utc)})
check("offset date-time numeric offset",
      "x: @1979-05-27T00:32:00.999-07:00\n",
      expected={'x': datetime(1979, 5, 27, 0, 32, 0, 999000,
                              tzinfo=timezone(timedelta(hours=-7)))})
check("lowercase t and z", "x: @1979-05-27t07:32:00z\n",
      expected={'x': datetime(1979, 5, 27, 7, 32, tzinfo=timezone.utc)})
check("local date-time", "x: @1979-05-27T07:32:00\n",
      expected={'x': datetime(1979, 5, 27, 7, 32)})
check("local date", "x: @1979-05-27\n", expected={'x': date(1979, 5, 27)})
check("local time", "x: @07:32:00\n", expected={'x': time(7, 32)})
check("local time with fractional seconds", "x: @07:32:00.5\n",
      expected={'x': time(7, 32, 0, 500000)})
check("date-time as anonymous map items (BRACE)",
      "{ @2026-01-01, @12:00:00 }",
      expected=[date(2026, 1, 1), time(12, 0)])
check("date as anonymous map items (INDENT)",
      "items:\n  @2026-01-01\n  @2026-01-02\n",
      expected={'items': [date(2026, 1, 1), date(2026, 1, 2)]})
check("space-separated offset date-time",
      "x: @1979-05-27 07:32:00Z\n",
      expected={'x': datetime(1979, 5, 27, 7, 32, tzinfo=timezone.utc)})
check("space-separated local date-time",
      "x: @1979-05-27 07:32:00\n",
      expected={'x': datetime(1979, 5, 27, 7, 32)})
check("date followed by a comment", "x: @2026-10-09 # today\n",
      expected={'x': date(2026, 10, 9)})

# 21. Date/time error paths
check("calendar-invalid date", "x: @2026-02-30\n",
      expect_error="Invalid date/time literal")
check("time hour out of range", "x: @25:00:00\n",
      expect_error="Invalid date/time literal")
check("malformed '@' literal", "x: @foo\n",
      expect_error="must introduce a well-formed date/time literal")
check("date-time must be delimiter-terminated", "x: @2026-10-09x\n",
      expect_error="must introduce a well-formed date/time literal")
check("space separator requires exactly one space",
      "x: @2026-10-09  12:13:14\n", expect_error="Expected key")
check("incomplete time part", "x: @2026-10-09T12:13\n",
      expect_error="must introduce a well-formed date/time literal")
check_raises("Config conflict: '@' reserved for date/time literals",
             lambda: flexconf.Config(key_value_separator='@'),
             "Invalid configuration")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
