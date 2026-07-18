from __future__ import annotations

import json
import threading
from pathlib import Path

import cv2
import numpy as np

from .base import PlateCandidate, RecognitionError
from .plate_text import build_plate_candidates


_REQUIRED_MODEL_FILES = (
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)


class PaddleOcrRecognizer:
    """PaddleOCR 复核适配器，兼容 PaddleOCR 2.x 和 3.x 的输出格式。"""

    def __init__(self, model_root: str = "models/paddleocr") -> None:
        self._engine = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        root = Path(model_root)
        self._det_model_dir = str(root / "PP-OCRv6_medium_det_infer")
        self._rec_model_dir = str(root / "PP-OCRv6_medium_rec_infer")
        self._textline_model_dir = str(root / "PP-LCNet_x1_0_textline_ori_infer")

    def _get_engine(self):
        if self._engine is None:
            with self._load_lock:
                if self._engine is None:
                    self._ensure_local_models()
                    try:
                        from paddleocr import PaddleOCR
                    except ImportError as exc:
                        raise RecognitionError(
                            "PaddleOCR 未安装。当前 Python 版本若无 PaddlePaddle wheel，"
                            "请使用 Python 3.13 安装 requirements-paddle.txt"
                        ) from exc
                    try:
                        try:
                            # PaddleOCR 3.x：关闭文档方向和文档矫正，保留文字行方向识别。
                            self._engine = PaddleOCR(
                                device="cpu",
                                enable_mkldnn=False,
                                lang="ch",
                                use_doc_orientation_classify=False,
                                use_doc_unwarping=False,
                                use_textline_orientation=True,
                                text_detection_model_name="PP-OCRv6_medium_det",
                                text_detection_model_dir=self._det_model_dir,
                                textline_orientation_model_name="PP-LCNet_x1_0_textline_ori",
                                textline_orientation_model_dir=self._textline_model_dir,
                                text_recognition_model_name="PP-OCRv6_medium_rec",
                                text_recognition_model_dir=self._rec_model_dir,
                            )
                        except TypeError:
                            # PaddleOCR 2.x 兼容参数。
                            self._engine = PaddleOCR(
                                lang="ch",
                                use_angle_cls=True,
                                show_log=False,
                                det_model_dir=self._det_model_dir,
                                rec_model_dir=self._rec_model_dir,
                            )
                    except Exception as exc:
                        raise RecognitionError(f"PaddleOCR 引擎加载失败: {exc}") from exc
        return self._engine

    def _ensure_local_models(self) -> None:
        missing = []
        for model_directory in (
            self._det_model_dir,
            self._rec_model_dir,
            self._textline_model_dir,
        ):
            for filename in _REQUIRED_MODEL_FILES:
                path = Path(model_directory) / filename
                if not path.is_file():
                    missing.append(str(path))
        if missing:
            raise RecognitionError(
                "PaddleOCR 本地模型文件不完整，未启动联网下载；缺少: "
                + ", ".join(missing)
            )

    def warmup(self) -> None:
        self._get_engine()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RecognitionError("上传内容不是有效的图片")

        try:
            with self._inference_lock:
                engine = self._get_engine()
                if hasattr(engine, "predict"):
                    output = engine.predict(image)
                else:
                    output = engine.ocr(image, cls=True)
        except RecognitionError:
            raise
        except Exception as exc:
            raise RecognitionError(f"PaddleOCR 识别失败: {exc}") from exc

        candidates = build_plate_candidates(list(_iter_text_scores(output)))

        if not candidates:
            raise RecognitionError("PaddleOCR 未识别到车牌，请上传更清晰、正对车牌的图片")
        return max(candidates, key=lambda candidate: candidate.confidence)


def _iter_text_scores(output: object):
    """提取 PaddleOCR 2.x/3.x 的文本和置信度。"""
    if output is None:
        return
    if isinstance(output, dict):
        texts = output.get("rec_texts") or output.get("texts") or output.get("txts") or []
        scores = output.get("rec_scores") or output.get("scores") or []
        for index, text in enumerate(texts):
            score = scores[index] if index < len(scores) else 0.0
            if isinstance(text, str):
                yield text, float(score)
        return
    if isinstance(output, str):
        try:
            yield from _iter_text_scores(json.loads(output))
        except json.JSONDecodeError:
            return
        return
    if isinstance(output, (list, tuple)):
        # PaddleOCR 2.x: [[box, (text, score)], ...]，外层还可能有 batch。
        if len(output) >= 2 and isinstance(output[0], str):
            yield output[0], float(output[1])
            return
        for item in output:
            yield from _iter_text_scores(item)
        return

    result = getattr(output, "json", None)
    if callable(result):
        yield from _iter_text_scores(result())
        return
    if result is not None:
        yield from _iter_text_scores(result)
        return
    result = getattr(output, "res", None)
    if result is not None:
        yield from _iter_text_scores(result)
