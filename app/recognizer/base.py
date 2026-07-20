from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RecognitionError(RuntimeError):
    """识别失败或识别引擎不可用。"""


@dataclass(frozen=True, slots=True)
class PlateBox:
    """检测模型返回的车牌轴对齐区域。坐标使用原图像素。"""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


@dataclass(frozen=True, slots=True)
class PlateCandidate:
    plate_number: str
    confidence: float
    box: PlateBox | None = None


class PlateRecognizer(Protocol):
    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        """从一张图片中识别车牌。"""
