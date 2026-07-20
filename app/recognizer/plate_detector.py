from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np

from .base import PlateBox, RecognitionError


class YoloV9PlateDetector:
    """使用 YOLOv9 ONNX 模型检测车牌区域，不负责识别文字。"""

    def __init__(self, model_path: str, minimum_confidence: float = 0.40) -> None:
        self._model_path = Path(model_path)
        self._minimum_confidence = minimum_confidence
        self._session = None
        self._input_name = None
        self._input_size: tuple[int, int] | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _get_session(self):
        if self._session is None:
            with self._load_lock:
                if self._session is None:
                    if not self._model_path.is_file():
                        raise RecognitionError(
                            f"车牌检测模型不存在: {self._model_path}。"
                            "请确认模型已下载到 models/plate_detector。"
                        )
                    try:
                        import onnxruntime as ort

                        session = ort.InferenceSession(
                            str(self._model_path),
                            providers=["CPUExecutionProvider"],
                        )
                    except Exception as exc:
                        raise RecognitionError(f"YOLO 车牌检测模型加载失败: {exc}") from exc

                    input_meta = session.get_inputs()[0]
                    height, width = input_meta.shape[-2:]
                    if not isinstance(height, int) or not isinstance(width, int) or height != width:
                        raise RecognitionError(
                            f"YOLO 车牌检测模型必须是固定正方形输入，实际为 {input_meta.shape}"
                        )
                    self._session = session
                    self._input_name = input_meta.name
                    self._input_size = (height, width)
        return self._session

    def warmup(self) -> None:
        self._get_session()

    def detect(self, image: np.ndarray) -> list[PlateBox]:
        if image is None or image.ndim != 3 or image.shape[2] != 3:
            raise RecognitionError("车牌检测只支持三通道彩色图片")

        session = self._get_session()
        assert self._input_name is not None
        assert self._input_size is not None
        tensor, scale, (pad_x, pad_y) = _preprocess(image, self._input_size)

        try:
            with self._inference_lock:
                output = session.run(None, {self._input_name: tensor})[0]
        except Exception as exc:
            raise RecognitionError(f"YOLO 车牌检测失败: {exc}") from exc

        boxes: list[PlateBox] = []
        for row in np.asarray(output, dtype=np.float32).reshape(-1, 7):
            # open-image-models 的 YOLOv9 end2end 输出为：batch, x1, y1, x2, y2, class, score。
            confidence = float(row[6])
            if confidence < self._minimum_confidence:
                continue
            x1 = int(round((float(row[1]) - pad_x) / scale))
            y1 = int(round((float(row[2]) - pad_y) / scale))
            x2 = int(round((float(row[3]) - pad_x) / scale))
            y2 = int(round((float(row[4]) - pad_y) / scale))
            x1, y1, x2, y2 = _clip_box(x1, y1, x2, y2, image.shape[1], image.shape[0])
            if x2 > x1 and y2 > y1:
                boxes.append(PlateBox(x1, y1, x2, y2, max(0.0, min(1.0, confidence))))
        return sorted(boxes, key=lambda box: box.confidence, reverse=True)


def _preprocess(image: np.ndarray, size: tuple[int, int]):
    height, width = image.shape[:2]
    target_height, target_width = size
    scale = min(target_width / width, target_height / height)
    resized_width = int(round(width * scale))
    resized_height = int(round(height * scale))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (target_width - resized_width) / 2
    pad_y = (target_height - resized_height) / 2
    left = int(round(pad_x - 0.1))
    right = int(round(pad_x + 0.1))
    top = int(round(pad_y - 0.1))
    bottom = int(round(pad_y + 0.1))
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    tensor = padded.transpose((2, 0, 1))[::-1].astype(np.float32) / 255.0
    return np.expand_dims(tensor, axis=0), scale, (pad_x, pad_y)


def _clip_box(x1: int, y1: int, x2: int, y2: int, width: int, height: int):
    return (
        max(0, min(width, x1)),
        max(0, min(height, y1)),
        max(0, min(width, x2)),
        max(0, min(height, y2)),
    )
