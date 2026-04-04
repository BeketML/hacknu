import json

from app.do_close_json import close_and_parse_json


def test_close_and_parse_complete():
    s = '{"actions": [{"_type": "message", "text": "hi"}]}'
    out = close_and_parse_json(s)
    assert out == json.loads(s)


def test_close_and_parse_truncated_object():
    s = '{"actions": [{"_type": "message", "text": "hi"'
    out = close_and_parse_json(s)
    assert out is not None
    assert "actions" in out


def test_close_incomplete_string():
    s = '{"a": "unclosed'
    out = close_and_parse_json(s)
    assert out is not None
    assert out.get("a") == "unclosed"


def test_escaped_quote_in_string():
    s = r'{"a": "say \"hi\""'
    out = close_and_parse_json(s)
    assert out is not None
