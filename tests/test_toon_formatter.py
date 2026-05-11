"""
Comprehensive tests for the internal TOON encoder.

Covers all spec sections implemented in infrastructure/formatters/toon.py:
- §2  Canonical number formatting
- §3  Normalisation (NaN, Inf, -0, non-JSON types)
- §5  Root form (object, array, primitive)
- §6  Array header syntax
- §7  String quoting and escaping
- §8  Object encoding / nesting
- §9  Array variants: primitive inline, arrays-of-arrays, tabular, mixed
- §10 Objects as list items
- §11 Delimiter options (comma, tab, pipe)
- §12 Indentation and whitespace invariants
- §13 Key folding (safe mode)
- API Validation (bad delimiter, bad indent)
"""
import math

import pytest

from pytest_beacon.infrastructure.formatters.toon import encode


# ===========================================================================
# Helpers
# ===========================================================================

def lines(s: str) -> list[str]:
    return s.split("\n")


# ===========================================================================
# §2 – Canonical number formatting
# ===========================================================================

class TestCanonicalNumbers:
    def test_integer_emitted_without_decimal(self):
        assert encode({"n": 42}) == "n: 42"

    def test_float_whole_value_emitted_as_integer(self):
        assert encode({"n": 3.0}) == "n: 3"

    def test_float_trailing_zeros_stripped(self):
        assert encode({"n": 1.5000}) == "n: 1.5"

    def test_negative_integer(self):
        assert encode({"n": -7}) == "n: -7"

    def test_negative_float(self):
        assert encode({"n": -3.14}) == "n: -3.14"

    def test_zero(self):
        assert encode({"n": 0}) == "n: 0"

    def test_large_integer(self):
        assert encode({"n": 9_007_199_254_740_992}) == "n: 9007199254740992"

    def test_small_float_no_exponent(self):
        result = encode({"n": 0.001})
        assert "e" not in result.lower()
        assert result == "n: 0.001"

    def test_large_float_no_exponent(self):
        result = encode({"n": 1_000_000.0})
        assert "e" not in result.lower()
        assert result == "n: 1000000"


# ===========================================================================
# §3 – Normalisation
# ===========================================================================

class TestNormalisation:
    def test_nan_becomes_null(self):
        assert encode({"x": float("nan")}) == "x: null"

    def test_positive_infinity_becomes_null(self):
        assert encode({"x": float("inf")}) == "x: null"

    def test_negative_infinity_becomes_null(self):
        assert encode({"x": float("-inf")}) == "x: null"

    def test_negative_zero_becomes_zero(self):
        assert encode({"x": -0.0}) == "x: 0"

    def test_none_becomes_null(self):
        assert encode({"x": None}) == "x: null"

    def test_set_becomes_array(self):
        result = encode({"x": {1}})
        assert "[1]:" in result

    def test_tuple_becomes_array(self):
        result = encode({"x": (1, 2)})
        assert "[2]: 1,2" in result

    def test_non_string_dict_keys_coerced_to_string(self):
        # Key 1 → "1" (string), then quoted because it looks numeric
        result = encode({1: "a"})
        assert '"1": a' in result


# ===========================================================================
# §5 – Root form
# ===========================================================================

class TestRootForm:
    def test_root_object(self):
        assert encode({"k": "v"}) == "k: v"

    def test_root_array_primitive(self):
        assert encode([1, 2, 3]) == "[3]: 1,2,3"

    def test_root_array_tabular(self):
        data = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        result = encode(data)
        assert result.startswith("[2]{id,name}:")

    def test_root_empty_object_is_empty_string(self):
        assert encode({}) == ""

    def test_root_empty_array(self):
        assert encode([]) == "[0]:"

    def test_root_null_primitive(self):
        assert encode(None) == "null"

    def test_root_bool_true(self):
        assert encode(True) == "true"

    def test_root_bool_false(self):
        assert encode(False) == "false"

    def test_root_integer(self):
        assert encode(42) == "42"

    def test_root_string_plain(self):
        assert encode("hello") == "hello"

    def test_root_string_quoted(self):
        assert encode("hello world") == "hello world"


# ===========================================================================
# §7 – String quoting rules
# ===========================================================================

class TestStringQuoting:
    def test_empty_string_quoted(self):
        assert encode({"k": ""}) == 'k: ""'

    def test_leading_space_quoted(self):
        assert encode({"k": " hi"}) == 'k: " hi"'

    def test_trailing_space_quoted(self):
        assert encode({"k": "hi "}) == 'k: "hi "'

    def test_true_literal_quoted(self):
        assert encode({"k": "true"}) == 'k: "true"'

    def test_false_literal_quoted(self):
        assert encode({"k": "false"}) == 'k: "false"'

    def test_null_literal_quoted(self):
        assert encode({"k": "null"}) == 'k: "null"'

    def test_numeric_like_string_quoted(self):
        assert encode({"k": "42"}) == 'k: "42"'

    def test_float_like_string_quoted(self):
        assert encode({"k": "3.14"}) == 'k: "3.14"'

    def test_leading_zero_string_quoted(self):
        assert encode({"k": "007"}) == 'k: "007"'

    def test_string_with_colon_quoted(self):
        assert encode({"k": "a:b"}) == 'k: "a:b"'

    def test_string_with_double_quote_quoted_and_escaped(self):
        assert encode({"k": 'say "hi"'}) == 'k: "say \\"hi\\""'

    def test_string_with_backslash_escaped(self):
        assert encode({"k": "a\\b"}) == 'k: "a\\\\b"'

    def test_string_with_newline_escaped(self):
        assert encode({"k": "a\nb"}) == 'k: "a\\nb"'

    def test_string_with_carriage_return_escaped(self):
        assert encode({"k": "a\rb"}) == 'k: "a\\rb"'

    def test_string_with_tab_escaped(self):
        assert encode({"k": "a\tb"}) == 'k: "a\\tb"'

    def test_string_with_bracket_quoted(self):
        assert encode({"k": "a[1]"}) == 'k: "a[1]"'

    def test_string_with_brace_quoted(self):
        assert encode({"k": "a{b}"}) == 'k: "a{b}"'

    def test_string_starting_with_hyphen_quoted(self):
        assert encode({"k": "-foo"}) == 'k: "-foo"'

    def test_hyphen_alone_quoted(self):
        assert encode({"k": "-"}) == 'k: "-"'

    def test_plain_string_not_quoted(self):
        assert encode({"k": "hello"}) == "k: hello"

    def test_string_with_internal_spaces_not_quoted(self):
        assert encode({"k": "hello world"}) == "k: hello world"

    def test_unicode_not_quoted(self):
        assert encode({"k": "héllo"}) == "k: héllo"

    def test_emoji_not_quoted(self):
        assert encode({"k": "hi 👋"}) == "k: hi 👋"

    def test_string_containing_delimiter_in_array_row_quoted(self):
        data = [{"a": "x,y", "b": 1}]
        result = encode(data)
        assert '"x,y"' in result

    def test_string_containing_tab_delimiter_in_row_quoted(self):
        data = [{"a": "x\ty", "b": 1}]
        result = encode(data, delimiter="\t")
        assert '"x\\ty"' in result


# ===========================================================================
# §7.3 – Key encoding
# ===========================================================================

class TestKeyEncoding:
    def test_simple_identifier_not_quoted(self):
        assert encode({"myKey": 1}) == "myKey: 1"

    def test_key_with_dot_not_quoted(self):
        assert encode({"my.key": 1}) == "my.key: 1"

    def test_key_with_underscore_not_quoted(self):
        assert encode({"my_key": 1}) == "my_key: 1"

    def test_key_with_hyphen_quoted(self):
        result = encode({"my-key": 1})
        assert result == '"my-key": 1'

    def test_key_starting_with_digit_quoted(self):
        result = encode({"1key": 1})
        assert result == '"1key": 1'

    def test_key_with_space_quoted(self):
        result = encode({"my key": 1})
        assert result == '"my key": 1'


# ===========================================================================
# §8 – Object nesting
# ===========================================================================

class TestObjectEncoding:
    def test_flat_object(self):
        assert encode({"a": 1, "b": 2}) == "a: 1\nb: 2"

    def test_nested_object(self):
        result = encode({"user": {"id": 1, "name": "Ada"}})
        assert result == "user:\n  id: 1\n  name: Ada"

    def test_deeply_nested_object(self):
        result = encode({"a": {"b": {"c": 1}}})
        assert result == "a:\n  b:\n    c: 1"

    def test_empty_nested_object(self):
        result = encode({"a": {}})
        assert result == "a:"

    def test_sibling_keys_preserved_in_order(self):
        result = encode({"z": 1, "a": 2, "m": 3})
        assert lines(result) == ["z: 1", "a: 2", "m: 3"]

    def test_custom_indent(self):
        result = encode({"a": {"b": 1}}, indent=4)
        assert result == "a:\n    b: 1"


# ===========================================================================
# §9.1 – Primitive inline arrays
# ===========================================================================

class TestPrimitiveArrays:
    def test_int_array(self):
        assert encode({"x": [1, 2, 3]}) == "x[3]: 1,2,3"

    def test_string_array(self):
        assert encode({"tags": ["a", "b"]}) == "tags[2]: a,b"

    def test_mixed_primitive_array(self):
        assert encode({"x": [1, "two", True, None]}) == "x[4]: 1,two,true,null"

    def test_empty_array(self):
        assert encode({"x": []}) == "x[0]:"

    def test_single_element_array(self):
        assert encode({"x": [42]}) == "x[1]: 42"

    def test_root_primitive_array(self):
        assert encode([1, 2, 3]) == "[3]: 1,2,3"

    def test_root_empty_array(self):
        assert encode([]) == "[0]:"


# ===========================================================================
# §9.2 – Arrays of primitive arrays
# ===========================================================================

class TestArraysOfArrays:
    def test_array_of_primitive_arrays(self):
        result = encode({"pairs": [[1, 2], [3, 4]]})
        expected = "pairs[2]:\n  - [2]: 1,2\n  - [2]: 3,4"
        assert result == expected

    def test_array_of_empty_inner_arrays(self):
        result = encode({"x": [[], []]})
        assert "- [0]:" in result

    def test_root_array_of_arrays(self):
        result = encode([[1, 2], [3, 4]])
        assert result.startswith("[2]:")
        assert "- [2]: 1,2" in result
        assert "- [2]: 3,4" in result


# ===========================================================================
# §9.3 – Tabular arrays
# ===========================================================================

class TestTabularArrays:
    def test_uniform_objects_tabular(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = encode({"users": data})
        assert result == "users[2]{id,name}:\n  1,Alice\n  2,Bob"

    def test_tabular_header_uses_first_object_key_order(self):
        data = [{"b": 2, "a": 1}, {"b": 4, "a": 3}]
        result = encode({"x": data})
        assert "{b,a}" in result

    def test_tabular_with_bool_values(self):
        data = [{"ok": True}, {"ok": False}]
        result = encode({"items": data})
        assert "true" in result
        assert "false" in result

    def test_tabular_with_null_values(self):
        data = [{"x": None}, {"x": None}]
        result = encode({"items": data})
        assert "null" in result

    def test_non_uniform_keys_not_tabular(self):
        data = [{"a": 1}, {"b": 2}]
        result = encode({"items": data})
        assert "{" not in result
        assert "- a: 1" in result

    def test_nested_value_disqualifies_tabular(self):
        data = [{"a": {"b": 1}}, {"a": {"b": 2}}]
        result = encode({"items": data})
        assert "{" not in result

    def test_array_value_disqualifies_tabular(self):
        data = [{"tags": [1, 2]}, {"tags": [3, 4]}]
        result = encode({"items": data})
        assert "{" not in result

    def test_root_tabular_array(self):
        data = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
        result = encode(data)
        assert result.startswith("[2]{id,val}:")
        assert "1,a" in result
        assert "2,b" in result

    def test_single_row_tabular(self):
        data = [{"x": 1, "y": 2}]
        result = encode({"pts": data})
        assert result == "pts[1]{x,y}:\n  1,2"


# ===========================================================================
# §9.4 – Mixed / non-uniform expanded list
# ===========================================================================

class TestMixedArrays:
    def test_mixed_primitive_and_object(self):
        result = encode({"items": [1, {"a": 2}, "three"]})
        assert "items[3]:" in result
        assert "- 1" in result
        assert "- a: 2" in result
        assert "- three" in result

    def test_array_of_non_uniform_objects(self):
        data = [{"a": 1}, {"b": 2}]
        result = encode({"x": data})
        assert "- a: 1" in result
        assert "- b: 2" in result

    def test_array_containing_nested_objects(self):
        data = [{"a": {"b": 1}}]
        result = encode({"x": data})
        assert "- a:" in result
        assert "b: 1" in result


# ===========================================================================
# §10 – Objects as list items
# ===========================================================================

class TestObjectsAsListItems:
    def test_first_field_on_hyphen_line(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        # non-tabular because keys are same but let's force it with an array value
        data = [{"id": 1, "tags": ["x"]}, {"id": 2, "tags": ["y"]}]
        result = encode({"items": data})
        assert "- id: 1" in result
        assert "- id: 2" in result

    def test_remaining_fields_at_depth_plus_one(self):
        data = [{"id": 1, "name": "Alice", "active": True}]
        # Force expanded list by adding a non-primitive field
        data_mixed = [{"id": 1, "info": {"role": "admin"}}, {"id": 2, "info": {"role": "user"}}]
        result = encode({"items": data_mixed})
        output_lines = lines(result)
        # "- id: 1" at depth+1 (2 spaces), "info:" at depth+2 (4 spaces)
        item_line = next(l for l in output_lines if "- id: 1" in l)
        info_line = next(l for l in output_lines if "info:" in l)
        assert item_line.startswith("  - ")
        assert info_line.startswith("    ")

    def test_empty_object_list_item_is_bare_hyphen(self):
        # A list of empty dicts is non-tabular (no keys); items render as bare "-"
        result = encode({"x": [{}, {}]})
        assert result == "x[2]:\n  -\n  -"

    def test_first_field_array_on_hyphen_line(self):
        # Per §10: when first field is an array, put header on hyphen line
        data = [{"tags": ["a", "b"], "name": "test"}]
        result = encode({"items": data})
        assert "- tags[2]: a,b" in result
        assert "name: test" in result

    def test_nested_list_item_indentation(self):
        # Use non-tabular data (nested value disqualifies tabular) to force expanded list
        result = encode({"outer": [{"a": 1, "nested": {"b": 2}}]})
        output_lines = lines(result)
        assert any(l.startswith("  - a: 1") for l in output_lines)
        assert any(l.startswith("    nested:") for l in output_lines)


# ===========================================================================
# §11 – Delimiter options
# ===========================================================================

class TestDelimiters:
    def test_tab_delimiter_in_primitive_array(self):
        # Per §6: tab symbol appears inside brackets for non-comma delimiters
        result = encode({"x": [1, 2, 3]}, delimiter="\t")
        assert "x[3\t]: 1\t2\t3" == result

    def test_pipe_delimiter_in_primitive_array(self):
        # Per §6: pipe symbol appears inside brackets
        result = encode({"x": [1, 2, 3]}, delimiter="|")
        assert "x[3|]: 1|2|3" == result

    def test_tab_delimiter_in_tabular_header_and_rows(self):
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = encode({"items": data}, delimiter="\t")
        # bracket contains tab; fields separated by tab
        assert "items[2\t]{a\tb}:" in result
        assert "1\t2" in result

    def test_pipe_delimiter_in_tabular(self):
        data = [{"a": 1, "b": 2}]
        result = encode({"items": data}, delimiter="|")
        assert "items[1|]{a|b}:" in result
        assert "1|2" in result

    def test_invalid_delimiter_raises(self):
        with pytest.raises(ValueError, match="delimiter"):
            encode({"x": 1}, delimiter=";")  # type: ignore[arg-type]

    def test_comma_delimiter_has_no_symbol_in_header(self):
        result = encode({"x": [1, 2]}, delimiter=",")
        assert "x[2]: 1,2" == result


# ===========================================================================
# §12 – Whitespace invariants
# ===========================================================================

class TestWhitespaceInvariants:
    def test_no_trailing_newline(self):
        result = encode({"a": 1})
        assert not result.endswith("\n")

    def test_no_trailing_spaces_on_any_line(self):
        data = {"a": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
        result = encode(data)
        for line in lines(result):
            assert line == line.rstrip(), f"Trailing space on line: {line!r}"

    def test_exactly_one_space_after_colon_in_kv(self):
        result = encode({"key": "value"})
        assert result == "key: value"

    def test_exactly_one_space_after_colon_before_inline_values(self):
        result = encode({"x": [1, 2]})
        assert result == "x[2]: 1,2"

    def test_invalid_indent_raises(self):
        with pytest.raises(ValueError, match="indent"):
            encode({"x": 1}, indent=0)

    def test_custom_indent_applied(self):
        result = encode({"a": {"b": 1}}, indent=4)
        assert result == "a:\n    b: 1"


# ===========================================================================
# §13.4 – Key folding
# ===========================================================================

class TestKeyFolding:
    def test_single_key_chain_folded(self):
        result = encode({"a": {"b": {"c": 1}}}, key_folding="safe")
        assert result == "a.b.c: 1"

    def test_multi_key_object_not_folded(self):
        result = encode({"a": {"b": 1, "c": 2}}, key_folding="safe")
        assert result == "a:\n  b: 1\n  c: 2"

    def test_chain_stops_at_multi_key_object(self):
        result = encode({"a": {"b": {"c": 1, "d": 2}}}, key_folding="safe")
        assert result == "a.b:\n  c: 1\n  d: 2"

    def test_chain_stops_at_array(self):
        result = encode({"a": {"b": [1, 2]}}, key_folding="safe")
        assert result == "a.b[2]: 1,2"

    def test_non_identifier_segment_not_folded(self):
        result = encode({"a": {"b-c": {"d": 1}}}, key_folding="safe")
        # "b-c" is not an IdentifierSegment; chain must not cross it
        assert "a:" in result
        assert '"b-c":' in result

    def test_flatten_depth_limits_segments(self):
        # depth=2 folds up to 2-segment paths; inner chains are then folded too
        result = encode({"a": {"b": {"c": {"d": 1}}}}, key_folding="safe", flatten_depth=2)
        # "a" + "b" → "a.b" (2 segments); then "c" + "d" → "c.d" (2 segments)
        assert result == "a.b:\n  c.d: 1"

    def test_key_folding_off_by_default(self):
        result = encode({"a": {"b": {"c": 1}}})
        assert result == "a:\n  b:\n    c: 1"

    def test_folded_key_with_tabular_array(self):
        data = {"a": {"b": {"items": [{"id": 1, "val": "x"}, {"id": 2, "val": "y"}]}}}
        result = encode(data, key_folding="safe")
        assert "a.b.items[2]{id,val}:" in result

    def test_folded_key_with_primitive_array(self):
        data = {"a": {"b": {"tags": ["x", "y"]}}}
        result = encode(data, key_folding="safe")
        assert "a.b.tags[2]: x,y" in result

    def test_collision_avoidance(self):
        # If folded key would collide with an existing sibling, keep unfolded
        data = {"a.b": 1, "a": {"b": 2}}
        result = encode(data, key_folding="safe")
        # Both keys must appear; no data lost
        assert "a.b" in result


# ===========================================================================
# Integration – realistic nested report structure
# ===========================================================================

class TestRealisticData:
    def test_report_encodes_without_error(self):
        # Use uniform test objects (same keys) to get tabular encoding
        report = {
            "results": {
                "tool": {"name": "pytest", "version": "9.0.0"},
                "summary": {"tests": 3, "passed": 2, "failed": 1, "start": 1000, "stop": 2000},
                "tests": [
                    {"name": "t1", "status": "passed", "duration": 10},
                    {"name": "t2", "status": "failed", "duration": 50},
                ],
                "environment": {"pythonVersion": "3.12.0"},
            }
        }
        result = encode(report)
        assert "results:" in result
        assert "tool:" in result
        assert "tests[2]{name,status,duration}:" in result

    def test_deeply_nested_console_output(self):
        report = {
            "consoleOutput": {
                "call": {
                    "stdout": {
                        "lines": ["line 1", "line 2"],
                        "truncated": False,
                        "omittedLines": 0,
                    }
                }
            }
        }
        result = encode(report)
        assert "consoleOutput:" in result
        assert "lines[2]: line 1,line 2" in result

    def test_general_logs_tabular_when_uniform(self):
        report = {
            "generalLogs": [
                {"level": "WARNING", "message": "slow", "logger": "app"},
                {"level": "ERROR", "message": "fail", "logger": "app"},
            ]
        }
        result = encode(report)
        assert "generalLogs[2]{level,message,logger}:" in result
        assert "WARNING,slow,app" in result

    def test_non_uniform_logs_expanded(self):
        report = {
            "logs": [
                {"level": "WARNING", "message": "a"},
                {"level": "ERROR", "message": "b", "extra": {"key": "val"}},
            ]
        }
        result = encode(report)
        # non-uniform (second has extra nested field), must use expanded list
        assert "{" not in result.split("logs[")[1].split(":")[0]
