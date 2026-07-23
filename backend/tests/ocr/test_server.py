import pytest

from app.services.ocr import server
from app.services.ocr.server import serialize_prediction


def test_server_serializes_paddle_result_without_leaking_input_metadata() -> None:
    payload = serialize_prediction(
        [
            {
                "res": {
                    "input_path": "/private/chart.png",
                    "rec_texts": ["营业收入"],
                    "rec_scores": [0.987],
                    "rec_polys": [[[1, 2], [10, 2], [10, 8], [1, 8]]],
                }
            }
        ]
    )

    assert payload == {
        "schema_version": "paddleocr-response.v1",
        "engine": {"name": "PaddleOCR", "version": "3.7.0"},
        "items": [
            {
                "text": "营业收入",
                "confidence": 0.987,
                "polygon": [[1.0, 2.0], [10.0, 2.0], [10.0, 8.0], [1.0, 8.0]],
            }
        ],
    }
    assert "/private/chart.png" not in str(payload)


def test_server_rejects_misaligned_result_arrays() -> None:
    with pytest.raises(ValueError, match="differ in length"):
        serialize_prediction(
            [
                {
                    "rec_texts": ["营业收入"],
                    "rec_scores": [],
                    "rec_polys": [[[1, 2], [10, 2], [10, 8], [1, 8]]],
                }
            ]
        )


def test_server_preloads_engine_before_listening(monkeypatch) -> None:
    events = []

    class StubServer:
        def __init__(self, *_args):
            events.append("listen")

        def serve_forever(self):
            events.append("serve")

    monkeypatch.setattr(server, "get_engine", lambda: events.append("engine"))
    monkeypatch.setattr(server, "HTTPServer", StubServer)

    server.main()

    assert events == ["engine", "listen", "serve"]
