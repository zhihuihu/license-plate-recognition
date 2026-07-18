from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RecognitionError(RuntimeError):
    """识别失败或识别引擎不可用。"""


@dataclass(frozen=True, slots=True)
class PlateCandidate:
    plate_number: str
    confidence: float


class PlateRecognizer(Protocol):
    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        """从一张图片中识别车牌。"""
