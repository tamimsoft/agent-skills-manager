"""Restricted YAML-subset frontmatter parser for SKILL.md files.

Supported constructs:
- ``---`` delimiters on their own line at the start of the file.
- ``key: value`` scalars.
- Quoted strings (single or double).
- ``>`` and ``|`` block scalars (folded/literal), indented body.
- Values containing colons (only the first colon separates key/value).
- ``#`` comments (full-line and trailing after a space).

Unsupported constructs produce a warning (``unsupported-yaml``) rather than a hard
error; the skill remains discoverable.
"""

import re

FRONTMATTER_DELIM = "---"
SUPPORTED_SCALARS = ("str", "block")


def _strip_comment(value):
    quote = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if index == 0 and char in ("'", '"'):
            quote = char
        elif char == "#" and index > 0 and value[index - 1].isspace():
            value = value[:index]
            break
    return value.rstrip()


def _parse_scalar(value):
    value = value.strip()
    if not value:
        return None
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    if value.lower() in ("true", "false", "null", "none"):
        # Keep as string for our purposes; callers coerce if needed.
        return value
    # Numeric-looking values kept as strings (frontmatter values are text).
    return value


def parse_frontmatter(text):
    """Parse frontmatter from the full text of a SKILL.md file.

    Returns a dict with keys:
      - ``status``: one of ``valid``, ``missing``, ``malformed``, ``partial``.
      - ``data``: dict of parsed key/value pairs (possibly empty).
      - ``warnings``: list of warning strings.
      - ``error``: error message if malformed, else None.
    """
    result = {"status": "missing", "data": {}, "warnings": [], "error": None}

    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return result

    # Find closing delimiter.
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return result

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        result["status"] = "malformed"
        result["error"] = "unterminated frontmatter (no closing ---)"
        return result

    body_lines = lines[1:end_idx]
    data = {}
    warnings = []
    i = 0
    n = len(body_lines)
    while i < n:
        line = body_lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in line or line.lstrip() != line:
            # indented line outside a block scalar context -> unsupported
            warnings.append("unsupported-yaml: indented line not in block scalar: %r" % line)
            i += 1
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key or not re.match(r"^[A-Za-z0-9_.-]+$", key):
            warnings.append("unsupported-yaml: invalid key %r" % key)
            i += 1
            continue

        # Block scalar
        if value in (">", "|", ">-", "|-", ">+", "|+"):
            block_lines = []
            i += 1
            while i < n and (body_lines[i].startswith(" ") or body_lines[i].startswith("\t") or body_lines[i].strip() == ""):
                block_lines.append(body_lines[i])
                i += 1
            if value.startswith(">"):
                # folded: join with spaces, collapse blank lines
                folded = []
                for bl in block_lines:
                    s = bl.strip()
                    if s == "":
                        folded.append("")
                    else:
                        if folded and folded[-1] != "" and not folded[-1].endswith(" "):
                            folded[-1] = folded[-1] + " " + s
                        else:
                            folded.append(s)
                data[key] = "\n".join(folded).strip()
            else:
                data[key] = "\n".join(bl.strip() for bl in block_lines).rstrip("\n")
            continue

        value = _strip_comment(value)
        scalar = _parse_scalar(value)
        i += 1
        if value and not value.startswith(("'", '"')):
            folded_lines = []
            while i < n:
                continuation = body_lines[i]
                if continuation.strip() == "":
                    if i + 1 < n and body_lines[i + 1].startswith((" ", "\t")):
                        folded_lines.append("")
                        i += 1
                        continue
                    break
                if not continuation.startswith((" ", "\t")):
                    break
                folded_lines.append(continuation.strip())
                i += 1
            if folded_lines:
                pieces = [str(scalar)] if scalar is not None else []
                for continuation in folded_lines:
                    if continuation:
                        pieces.append(continuation)
                    elif pieces:
                        pieces.append("\n")
                scalar = " ".join(pieces).replace(" \n ", "\n").replace("\n ", "\n").strip()
        data[key] = scalar

    # Determine status
    result["data"] = data
    result["warnings"] = warnings
    if not data:
        result["status"] = "partial"
    elif "name" in data and "description" in data and data.get("name") and data.get("description"):
        result["status"] = "valid"
    elif "name" in data or "description" in data:
        result["status"] = "partial"
    else:
        result["status"] = "partial"

    if warnings:
        # Keep status but note; unsupported constructs are warnings not errors.
        pass

    return result


def frontmatter_status(text):
    r = parse_frontmatter(text)
    return r["status"]