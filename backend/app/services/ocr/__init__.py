from app.services.ocr.client import PaddleOcrClient
from app.services.ocr.contracts import (
    OcrEngine,
    OcrItem,
    OcrResult,
    OcrServiceError,
)

__all__ = [
    "OcrEngine",
    "OcrItem",
    "OcrResult",
    "OcrServiceError",
    "PaddleOcrClient",
]
