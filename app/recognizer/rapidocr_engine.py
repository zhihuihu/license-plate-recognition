from __future__ import annotations

import threading

import cv2
import numpy as np

from .base import PlateCandidate, RecognitionError
from .plate_text import build_plate_candidates


class RapidOcrRecognizer:
    """RapidOCR 适配器，默认使用 ONNX Runtime 在 CPU 上推理。"""

    def __init__(self) -> None:
        self._engine = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _get_engine(self):
        if self._engine is None:
            with self._load_lock:
                if self._engine is None:
                    try:
                        from rapidocr import RapidOCR
                    except ImportError as exc:
                        raise RecognitionError(
                            "OCR 引擎未安装，请先安装 rapidocr 和 onnxruntime"
                        ) from exc
                    try:
                        self._engine = RapidOCR()
                    except Exception as exc:
                        raise RecognitionError(f"OCR 引擎加载失败: {exc}") from exc
        return self._engine

    def warmup(self) -> None:
        self._get_engine()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RecognitionError("上传内容不是有效的图片")

        try:
            # 同一个 OCR 实例不让多个线程同时推理，避免底层 ONNX Runtime
            # 在低配机器上争抢资源；生产环境可通过多进程横向扩展。
            with self._inference_lock:
                output = self._get_engine()(image)
        except RecognitionError:
            raise
        except Exception as exc:
            raise RecognitionError(f"OCR 识别失败: {exc}") from exc

        candidates = build_plate_candidates(list(_iter_output_lines(output)))

        if not candidates:
            raise RecognitionError("未识别到车牌，请上传更清晰、正对车牌的图片")
        return max(candidates, key=lambda candidate: candidate.confidence)


def _iter_output_lines(output: object):
    """读取 RapidOCROutput，也兼容 dict 和旧版 tuple 结果。"""
    if output is None:
        return

    if isinstance(output, (list, tuple)):
        # 新版输出通常是 dataclass；旧版可能直接返回 (result, elapse)。
        if len(output) == 2 and isinstance(output[0], (list, tuple)):
            yield from _iter_output_lines(output[0])
            return
        for item in output:
            yield from _iter_output_lines(item)
        return

    if isinstance(output, dict):
        texts = output.get("txts")
        if texts is None:
            texts = output.get("texts")
        if texts is None:
            texts = []
        scores = output.get("scores")
        if scores is None:
            scores = output.get("rec_scores")
        if scores is None:
            scores = []
        for index, text in enumerate(texts):
            score = scores[index] if index < len(scores) else 0.0
            if isinstance(text, str):
                yield text, float(score)
        return

    texts = getattr(output, "txts", None)
    scores = getattr(output, "scores", None)
    if texts is not None:
        if scores is None:
            scores = ()
        for index, text in enumerate(texts):
            score = scores[index] if index < len(scores) else 0.0
            if isinstance(text, str):
                yield text, float(score)
