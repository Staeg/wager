from src.protocol import encode, decode


class TestEncodeDecode:
    def test_roundtrip_simple(self):
        msg = {"type": "join", "player_name": "Test"}
        assert decode(encode(msg)) == msg

    def test_roundtrip_nested(self):
        msg = {
            "type": "state_update",
            "armies": [
                {"player": 1, "units": [["Page", 5]], "pos": [1, 2], "exhausted": False}
            ],
            "gold": {"1": 100},
        }
        result = decode(encode(msg))
        assert result["type"] == "state_update"
        assert result["armies"][0]["player"] == 1

    def test_roundtrip_empty(self):
        msg = {}
        assert decode(encode(msg)) == msg
