"""
TOON (Token-Oriented Object Notation) encoder.

Implements the TOON v3.0 specification:
https://github.com/toon-format/spec/blob/main/SPEC.md

Key rules implemented:
- §2:  Canonical number form (no exponent, no trailing zeros, integer if whole)
- §3:  Non-JSON type normalisation (NaN/Inf → null, -0 → 0)
- §5:  Root-form determination
- §6:  Array header syntax: key[N]: / key[N]{f1,f2}:
- §7:  String quoting and escaping (only \\, ", \\n, \\r, \\t)
- §8:  Object encoding (indentation-based nesting)
- §9:  Array encoding — primitive inline (§9.1), arrays-of-arrays (§9.2),
       tabular (§9.3), mixed/non-uniform expanded list (§9.4)
- §10: Objects as list items (first field on hyphen line)
- §11: Delimiter scoping (comma default, tab, pipe)
- §12: Indentation (spaces only, no trailing spaces, no trailing newline)
- §13: keyFolding option ("off" | "safe")
"""
from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_VALID_DELIMITERS = (",", "\t", "|")
_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")
_LEADING_ZERO_RE = re.compile(r"^0\d+$")


def encode(
    value: Any,
    *,
    indent: int = 2,
    delimiter: Literal[",", "\t", "|"] = ",",
    key_folding: Literal["off", "safe"] = "off",
    flatten_depth: int | None = None,
) -> str:
    """Encode *value* to a TOON-formatted string.

    Args:
        value: Any JSON-serialisable value (object, array, or primitive).
               Non-JSON values are normalised per §3.
        indent: Spaces per indentation level (default 2).
        delimiter: Field delimiter — comma (default), tab, or pipe.
        key_folding: ``"safe"`` collapses single-key object chains into dotted
                     paths.  ``"off"`` (default) emits standard nesting.
        flatten_depth: Maximum number of path segments to fold when
                       ``key_folding="safe"``.  ``None`` means unlimited.

    Returns:
        A TOON-formatted string with no trailing newline or spaces.
    """
    if delimiter not in _VALID_DELIMITERS:
        raise ValueError(f"delimiter must be one of {_VALID_DELIMITERS!r}, got {delimiter!r}")
    if indent < 1:
        raise ValueError(f"indent must be >= 1, got {indent}")

    normalised = _normalise(value)

    if key_folding == "safe":
        normalised = _fold_keys(normalised, flatten_depth)

    lines = _encode_root(normalised, " " * indent, delimiter)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# §3 – Normalisation
# ---------------------------------------------------------------------------

def _normalise(value: Any) -> Any:
    """Recursively normalise host types to JSON-compatible values."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        if value == 0.0:
            return 0  # -0 → 0
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, set):
        return [_normalise(item) for item in value]
    # Fallback: try dict-like, else null
    try:
        return {str(k): _normalise(v) for k, v in vars(value).items()}
    except TypeError:
        return None


# ---------------------------------------------------------------------------
# §13.4 – Key folding
# ---------------------------------------------------------------------------

def _fold_keys(value: Any, max_depth: int | None) -> Any:
    """Recursively fold single-key object chains into dotted-path keys."""
    if not isinstance(value, dict):
        if isinstance(value, list):
            return [_fold_keys(item, max_depth) for item in value]
        return value

    result: dict[str, Any] = {}
    for k, v in value.items():
        folded_key, folded_val = _fold_chain(k, v, max_depth)
        folded_val = _fold_keys(folded_val, max_depth)
        # Collision avoidance: if folded key already exists, keep unfolded
        if folded_key in result:
            result[k] = folded_val
        else:
            result[folded_key] = folded_val
    return result


def _fold_chain(key: str, value: Any, max_depth: int | None) -> tuple[str, Any]:
    """Walk a single-key chain and return the folded key + leaf value."""
    if not _IDENTIFIER_PATTERN.match(key):
        return key, value

    segments = [key]
    current = value

    while (
        isinstance(current, dict)
        and len(current) == 1
        and (max_depth is None or len(segments) < max_depth)
    ):
        child_key = next(iter(current))
        if not _IDENTIFIER_PATTERN.match(child_key):
            break
        segments.append(child_key)
        current = current[child_key]

    if len(segments) == 1:
        return key, value

    return ".".join(segments), current


# ---------------------------------------------------------------------------
# §2 – Canonical number formatting
# ---------------------------------------------------------------------------

def _format_number(v: int | float) -> str:
    """Return canonical TOON decimal form for a number."""
    if isinstance(v, bool):
        # bool is a subclass of int — handled before reaching here, but guard anyway
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    # float
    if v == int(v):
        return str(int(v))
    s = repr(v)
    if "e" in s or "E" in s:
        s = format(Decimal(s), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


# ---------------------------------------------------------------------------
# §7 – String quoting and escaping
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    """Apply the five TOON escape sequences to *s*."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


def _needs_quoting(s: str, active_delimiter: str) -> bool:
    """Return True when *s* must be quoted per §7.2."""
    if not s:
        return True
    if s[0] == " " or s[-1] == " ":
        return True
    if s in ("true", "false", "null"):
        return True
    if _NUMERIC_RE.match(s):
        return True
    if _LEADING_ZERO_RE.match(s):
        return True
    for ch in (":", '"', "\\", "[", "]", "{", "}"):
        if ch in s:
            return True
    if "\n" in s or "\r" in s or "\t" in s:
        return True
    if active_delimiter in s:
        return True
    if s[0] == "-":
        return True
    return False


def _quote_string(s: str, active_delimiter: str) -> str:
    """Return a quoted or bare string value per §7.2."""
    if _needs_quoting(s, active_delimiter):
        return '"' + _escape(s) + '"'
    return s


def _encode_key(k: str) -> str:
    """Encode an object key per §7.3."""
    if _KEY_PATTERN.match(k):
        return k
    return '"' + _escape(k) + '"'


# ---------------------------------------------------------------------------
# §7.2 – Primitive value formatting
# ---------------------------------------------------------------------------

def _fmt_primitive(v: Any, active_delimiter: str) -> str:
    """Format a primitive for inline use (array cell or object field value)."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _format_number(v)
    if isinstance(v, str):
        return _quote_string(v, active_delimiter)
    return "null"


def _is_primitive(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


# ---------------------------------------------------------------------------
# §9.3 – Tabular detection
# ---------------------------------------------------------------------------

def _is_tabular(lst: list) -> bool:
    """Return True when every element is an object with identical keys and
    all-primitive values (§9.3 tabular requirements)."""
    if not lst:
        return False
    if not all(isinstance(item, dict) for item in lst):
        return False
    keys = list(lst[0].keys())
    if not keys:  # lists of empty objects are not tabular
        return False
    for item in lst:
        if list(item.keys()) != keys:
            return False
        if not all(_is_primitive(item[k]) for k in keys):
            return False
    return True


# ---------------------------------------------------------------------------
# §5 – Root form
# ---------------------------------------------------------------------------

def _encode_root(value: Any, indent_str: str, delimiter: str) -> list[str]:
    """Return lines for the root value."""
    if isinstance(value, dict):
        if not value:
            return []
        return _encode_object_fields(value, indent_str, 0, delimiter)

    if isinstance(value, list):
        return _encode_array_root(value, indent_str, 0, delimiter)

    # Single primitive root
    return [_fmt_primitive(value, delimiter)]


# ---------------------------------------------------------------------------
# §8 – Object encoding
# ---------------------------------------------------------------------------

def _encode_object_fields(
    obj: dict,
    indent_str: str,
    depth: int,
    delimiter: str,
) -> list[str]:
    """Encode all key-value pairs of *obj* at *depth*."""
    prefix = indent_str * depth
    lines: list[str] = []

    for k, v in obj.items():
        key_str = _encode_key(k)
        if isinstance(v, dict):
            lines.append(f"{prefix}{key_str}:")
            lines.extend(_encode_object_fields(v, indent_str, depth + 1, delimiter))
        elif isinstance(v, list):
            lines.extend(_encode_named_array(key_str, v, indent_str, depth, delimiter))
        else:
            lines.append(f"{prefix}{key_str}: {_fmt_primitive(v, delimiter)}")

    return lines


# ---------------------------------------------------------------------------
# §9 – Array encoding (named variant used inside objects)
# ---------------------------------------------------------------------------

def _delim_sym(delimiter: str) -> str:
    """Return the delimiter symbol for the bracket segment (§6).

    Comma has no symbol (it is the default); tab and pipe are explicit.
    """
    if delimiter == ",":
        return ""
    return delimiter


def _encode_named_array(
    key_str: str,
    lst: list,
    indent_str: str,
    depth: int,
    delimiter: str,
) -> list[str]:
    """Encode a named array at *depth* (key appears before the header)."""
    prefix = indent_str * depth
    next_prefix = indent_str * (depth + 1)
    n = len(lst)
    sym = _delim_sym(delimiter)

    # Empty array
    if n == 0:
        return [f"{prefix}{key_str}[0]:"]

    # §9.1 – Primitive inline array
    if all(_is_primitive(item) for item in lst):
        vals = delimiter.join(_fmt_primitive(item, delimiter) for item in lst)
        return [f"{prefix}{key_str}[{n}{sym}]: {vals}"]

    # §9.2 – Array of primitive arrays
    if all(
        isinstance(item, list) and all(_is_primitive(x) for x in item)
        for item in lst
    ):
        lines = [f"{prefix}{key_str}[{n}{sym}]:"]
        for inner in lst:
            inner_sym = _delim_sym(delimiter)
            if inner:
                inner_vals = delimiter.join(_fmt_primitive(x, delimiter) for x in inner)
                lines.append(f"{next_prefix}- [{len(inner)}{inner_sym}]: {inner_vals}")
            else:
                lines.append(f"{next_prefix}- [0]:")
        return lines

    # §9.3 – Tabular array of uniform objects
    if _is_tabular(lst):
        keys = list(lst[0].keys())
        header = delimiter.join(_encode_key(k) for k in keys)
        lines = [f"{prefix}{key_str}[{n}{sym}]{{{header}}}:"]
        for row in lst:
            row_vals = delimiter.join(_fmt_primitive(row[k], delimiter) for k in keys)
            lines.append(f"{next_prefix}{row_vals}")
        return lines

    # §9.4 – Mixed / non-uniform expanded list
    lines = [f"{prefix}{key_str}[{n}{sym}]:"]
    for item in lst:
        lines.extend(_encode_list_item(item, indent_str, depth + 1, delimiter))
    return lines


def _encode_array_root(
    lst: list,
    indent_str: str,
    depth: int,
    delimiter: str,
) -> list[str]:
    """Encode a root-level or unnamed array (no key prefix)."""
    prefix = indent_str * depth
    next_prefix = indent_str * (depth + 1)
    n = len(lst)
    sym = _delim_sym(delimiter)

    if n == 0:
        return [f"{prefix}[0]:"]

    if all(_is_primitive(item) for item in lst):
        vals = delimiter.join(_fmt_primitive(item, delimiter) for item in lst)
        return [f"{prefix}[{n}{sym}]: {vals}"]

    if all(
        isinstance(item, list) and all(_is_primitive(x) for x in item)
        for item in lst
    ):
        lines = [f"{prefix}[{n}{sym}]:"]
        for inner in lst:
            inner_sym = _delim_sym(delimiter)
            if inner:
                inner_vals = delimiter.join(_fmt_primitive(x, delimiter) for x in inner)
                lines.append(f"{next_prefix}- [{len(inner)}{inner_sym}]: {inner_vals}")
            else:
                lines.append(f"{next_prefix}- [0]:")
        return lines

    if _is_tabular(lst):
        keys = list(lst[0].keys())
        header = delimiter.join(_encode_key(k) for k in keys)
        lines = [f"{prefix}[{n}{sym}]{{{header}}}:"]
        for row in lst:
            row_vals = delimiter.join(_fmt_primitive(row[k], delimiter) for k in keys)
            lines.append(f"{next_prefix}{row_vals}")
        return lines

    lines = [f"{prefix}[{n}{sym}]:"]
    for item in lst:
        lines.extend(_encode_list_item(item, indent_str, depth + 1, delimiter))
    return lines


# ---------------------------------------------------------------------------
# §10 – Objects as list items
# ---------------------------------------------------------------------------

def _encode_list_item(
    value: Any,
    indent_str: str,
    depth: int,
    delimiter: str,
) -> list[str]:
    """Encode a single list item, producing one or more ``- …`` lines."""
    prefix = indent_str * depth
    next_prefix = indent_str * (depth + 1)

    # --- dict item ---
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}-"]

        items = list(value.items())
        first_key, first_val = items[0]
        key_str = _encode_key(first_key)
        rest = items[1:]
        lines: list[str] = []

        if isinstance(first_val, list):
            # First field is an array — per §10 the header goes on the hyphen line
            array_lines = _encode_named_array(key_str, first_val, indent_str, depth, delimiter)
            # Strip the leading indent from the first array line and prepend "- "
            first_line_content = array_lines[0][len(prefix):]
            lines.append(f"{prefix}- {first_line_content}")
            lines.extend(array_lines[1:])
        elif isinstance(first_val, dict):
            lines.append(f"{prefix}- {key_str}:")
            lines.extend(_encode_object_fields(first_val, indent_str, depth + 1, delimiter))
        else:
            lines.append(f"{prefix}- {key_str}: {_fmt_primitive(first_val, delimiter)}")

        # Remaining fields are siblings at depth+1
        for k, v in rest:
            k_str = _encode_key(k)
            if isinstance(v, dict):
                lines.append(f"{next_prefix}{k_str}:")
                lines.extend(_encode_object_fields(v, indent_str, depth + 2, delimiter))
            elif isinstance(v, list):
                lines.extend(_encode_named_array(k_str, v, indent_str, depth + 1, delimiter))
            else:
                lines.append(f"{next_prefix}{k_str}: {_fmt_primitive(v, delimiter)}")

        return lines

    # --- list item that is itself a list ---
    if isinstance(value, list):
        if all(_is_primitive(item) for item in value):
            vals = delimiter.join(_fmt_primitive(item, delimiter) for item in value)
            return [f"{prefix}- [{len(value)}]: {vals}"]
        # Non-primitive inner list: emit header on hyphen line
        inner_lines = _encode_array_root(value, indent_str, depth, delimiter)
        first_line_content = inner_lines[0][len(prefix):]
        return [f"{prefix}- {first_line_content}"] + inner_lines[1:]

    # --- primitive item ---
    return [f"{prefix}- {_fmt_primitive(value, delimiter)}"]
