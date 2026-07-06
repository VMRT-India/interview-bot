import json

_decoder = json.JSONDecoder()


def _strip_stray_escapes(s: str) -> str:
    """Drop backslash-escape sequences that appear outside string literals.

    Some LLMs (observed with gpt-oss-120b on Groq) pretty-print JSON using
    literal backslash-n/backslash-t as whitespace between tokens, which is
    invalid outside a string per the JSON grammar even though the model's
    output is otherwise well-formed and complete.
    """
    result = []
    in_string = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if in_string:
            if c == "\\" and i + 1 < n:
                result.append(c)
                result.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            result.append(c)
            i += 1
        else:
            if c == '"':
                in_string = True
                result.append(c)
                i += 1
            elif c == "\\" and i + 1 < n:
                i += 2
                continue
            else:
                result.append(c)
                i += 1
    return "".join(result)


def _decode_first_value(raw: str, open_char: str, not_found_msg: str) -> object:
    """Parse only the first complete JSON value starting at open_char.

    Ignores any trailing content after that value — some LLMs append notes
    or duplicate content after a complete, valid JSON object/array even when
    instructed to return JSON only, which json.loads() would reject outright
    via "Extra data" even though the actual payload is well-formed.
    """
    start = raw.find(open_char)
    if start == -1:
        raise ValueError(not_found_msg)
    try:
        obj, _ = _decoder.raw_decode(raw, start)
        return obj
    except json.JSONDecodeError:
        repaired = _strip_stray_escapes(raw[start:])
        obj, _ = _decoder.raw_decode(repaired, 0)
        return obj


def extract_json(raw: str) -> dict:
    return _decode_first_value(raw, "{", "No JSON object found in LLM response")


def extract_json_array(raw: str) -> list[dict]:
    return _decode_first_value(raw, "[", "No JSON array found in LLM response")
