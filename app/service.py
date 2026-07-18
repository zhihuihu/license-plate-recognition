from __future__ import annotations

import time
from datetime import datetime, timezone

from .recognizer.base import PlateRecognizer
from .schemas import RecognitionResponse


class RecognitionService:
    def __init__(self, recognizer: PlateRecognizer) -> None:
        self._recognizer = recognizer

    def warmup(self) -> None:
        warmup = getattr(self._recognizer, "warmup", None)
        if callable(warmup):
            warmup()

    def recognize(self, image_bytes: bytes, request_id: str = "unknown") -> RecognitionResponse:
        started = time.perf_counter()
        candidate = self._recognizer.recognize(image_bytes)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return RecognitionResponse(
            request_id=request_id,
            plate_number=candidate.plate_number,
            recognized_at=datetime.now(timezone.utc),
            processing_time_ms=elapsed_ms,
            confidence=round(candidate.confidence, 4),
        )
