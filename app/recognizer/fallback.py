from __future__ import annotations

import logging

from .base import PlateCandidate, PlateRecognizer, RecognitionError


logger = logging.getLogger("license_plate.recognizer")


class FallbackRecognizer:
    """主模型失败时使用本地备用模型，不向任何远程服务发送图片。"""

    def __init__(
        self,
        primary: PlateRecognizer,
        fallback: PlateRecognizer,
        minimum_confidence: float = 0.75,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._minimum_confidence = minimum_confidence

    def warmup(self) -> None:
        primary_warmup = getattr(self._primary, "warmup", None)
        if callable(primary_warmup):
            primary_warmup()

        # 备用引擎可以是可选依赖（例如 PaddleOCR 在当前 Python 版本下
        # 没有预编译包），不能因为它不可用而阻止主引擎启动。
        fallback_warmup = getattr(self._fallback, "warmup", None)
        if callable(fallback_warmup):
            try:
                fallback_warmup()
            except RecognitionError as exc:
                logger.warning("fallback_recognizer_warmup_failed error=%s", exc)

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        primary_candidate: PlateCandidate | None = None
        try:
            primary_candidate = self._primary.recognize(image_bytes)
            if primary_candidate.confidence >= self._minimum_confidence:
                return primary_candidate
            logger.warning(
                "primary_recognizer_low_confidence confidence=%.4f threshold=%.4f",
                primary_candidate.confidence,
                self._minimum_confidence,
            )
        except RecognitionError as primary_error:
            logger.warning("primary_recognizer_failed error=%s", primary_error)
            primary_error_to_raise = primary_error
        else:
            primary_error_to_raise = None
        try:
            return self._fallback.recognize(image_bytes)
        except RecognitionError as fallback_error:
            if primary_candidate is not None:
                return primary_candidate
            raise RecognitionError(
                f"主模型和本地备用模型均未识别成功: {fallback_error}"
            ) from primary_error_to_raise
