from demo.events import canonical_json


def test_canonical_json_sorted_compact_utf8():
    assert canonical_json({"b": 1, "a": "café"}) == '{"a":"café","b":1}'.encode()
