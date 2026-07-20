from __future__ import annotations

import cv2
import numpy as np

from .base import PlateCandidate, PlateBox, RecognitionError
from .plate_detector import YoloV9PlateDetector
from .paddleocr_engine import PaddleOcrRecognizer


class DetectedPaddleOcrRecognizer:
    """先检测车牌区域，再对每块车牌使用 PaddleOCR 识别。"""

    def __init__(
        self,
        detector: YoloV9PlateDetector,
        ocr: PaddleOcrRecognizer,
        padding_ratio: float = 0.08,
    ) -> None:
        self._detector = detector
        self._ocr = ocr
        self._padding_ratio = max(0.0, min(0.25, padding_ratio))

    def warmup(self) -> None:
        self._detector.warmup()
        self._ocr.warmup()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RecognitionError("上传内容不是有效的图片")

        regions = self._detector.detect(image)
        if not regions:
            raise RecognitionError("YOLO 未检测到车牌，请上传包含清晰车牌的图片")

        candidates: list[PlateCandidate] = []
        for region in regions:
            crop = _crop_with_padding(image, region, self._padding_ratio)
            try:
                candidate = self._ocr.recognize_image(crop)
            except RecognitionError:
                continue
            candidates.append(
                PlateCandidate(
                    plate_number=candidate.plate_number,
                    confidence=min(candidate.confidence, region.confidence),
                    box=region,
                )
            )

        if not candidates:
            raise RecognitionError("已定位车牌，但 PaddleOCR 未识别到有效车牌号")
        return max(candidates, key=lambda candidate: candidate.confidence)


def _crop_with_padding(image: np.ndarray, box: PlateBox, padding_ratio: float) -> np.ndarray:
    width = box.x2 - box.x1
    height = box.y2 - box.y1
    pad_x = int(round(width * padding_ratio))
    pad_y = int(round(height * padding_ratio))
    x1 = max(0, box.x1 - pad_x)
    y1 = max(0, box.y1 - pad_y)
    x2 = min(image.shape[1], box.x2 + pad_x)
    y2 = min(image.shape[0], box.y2 + pad_y)
    return image[y1:y2, x1:x2]
