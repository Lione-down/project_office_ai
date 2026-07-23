from functools import lru_cache
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import tempfile
from typing import Any


MAX_IMAGE_BYTES = int(os.environ.get("OFFICE_AI_MAX_IMAGE_BYTES", 20 * 1024 * 1024))
MAX_OCR_ITEMS = int(os.environ.get("OFFICE_AI_MAX_OCR_ITEMS", 5000))
OCR_ENGINE_VERSION = "3.7.0"
CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@lru_cache(maxsize=1)
def get_engine():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )


def _plain_value(value: Any):
    return value.tolist() if hasattr(value, "tolist") else value


def serialize_prediction(predictions) -> dict[str, Any]:
    items = []
    for prediction in predictions:
        payload = prediction["res"] if "res" in prediction else prediction
        texts = _plain_value(payload.get("rec_texts", []))
        scores = _plain_value(payload.get("rec_scores", []))
        polygons = _plain_value(payload.get("rec_polys", payload.get("dt_polys", [])))
        if not (len(texts) == len(scores) == len(polygons)):
            raise ValueError("PaddleOCR result arrays differ in length")
        for text, score, polygon in zip(texts, scores, polygons, strict=True):
            if not str(text).strip():
                continue
            if len(items) >= MAX_OCR_ITEMS:
                raise ValueError("PaddleOCR item budget exceeded")
            items.append(
                {
                    "text": str(text),
                    "confidence": float(score),
                    "polygon": [
                        [max(0.0, float(point[0])), max(0.0, float(point[1]))]
                        for point in polygon
                    ],
                }
            )
    return {
        "schema_version": "paddleocr-response.v1",
        "engine": {"name": "PaddleOCR", "version": OCR_ENGINE_VERSION},
        "items": items,
    }


class OcrRequestHandler(BaseHTTPRequestHandler):
    server_version = "OfficeAiOcr/1.0"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._json_response(404, {"error": "not_found"})
            return
        self._json_response(200, {"status": "ok", "engine": OCR_ENGINE_VERSION})

    def do_POST(self) -> None:
        if self.path != "/v1/ocr":
            self._json_response(404, {"error": "not_found"})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
        extension = CONTENT_TYPES.get(content_type)
        content_length = self._content_length()
        if extension is None or content_length is None:
            self._json_response(400, {"error": "request_invalid"})
            return
        payload = self.rfile.read(content_length)
        expected_sha256 = self.headers.get("X-Content-Sha256", "")
        if (
            len(payload) != content_length
            or sha256(payload).hexdigest() != expected_sha256
        ):
            self._json_response(422, {"error": "content_integrity_mismatch"})
            return
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as source:
                source.write(payload)
                temporary_path = Path(source.name)
            result = serialize_prediction(get_engine().predict(str(temporary_path)))
            self._json_response(200, result)
        except ValueError:
            self._json_response(422, {"error": "ocr_result_invalid"})
        except Exception:
            self._json_response(503, {"error": "ocr_unavailable"})
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _content_length(self) -> int | None:
        try:
            value = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        return value if 0 < value <= MAX_IMAGE_BYTES else None

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args) -> None:
        return


def main() -> None:
    get_engine()
    server = HTTPServer(("0.0.0.0", 8080), OcrRequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
