from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .base import PlateBox, PlateCandidate, RecognitionError
from .plate_text import normalize_plate


_PLATE_CHARACTERS = (
    "#京沪津渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新"
    "学警港澳挂使领民航危0123456789ABCDEFGHJKLMNPQRSTUVWXYZ险品"
)


@dataclass(frozen=True, slots=True)
class _Yolo26Detection:
    box: PlateBox
    landmarks: np.ndarray
    plate_type: int


class Yolo26PlateRecognizer:
    """YOLO26 Pose 车牌检测 + 四角矫正 + 专用字符识别。"""

    def __init__(
        self,
        detector_model_path: str,
        recognizer_model_path: str,
        minimum_confidence: float = 0.20,
    ) -> None:
        self._detector_model_path = Path(detector_model_path)
        self._recognizer_model_path = Path(recognizer_model_path)
        self._minimum_confidence = minimum_confidence
        self._detector_session = None
        self._recognizer_session = None
        self._detector_input_name = None
        self._recognizer_input_name = None
        self._detector_output_name = None
        self._recognizer_output_names: tuple[str, str] | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _get_sessions(self):
        if self._detector_session is None or self._recognizer_session is None:
            with self._load_lock:
                if self._detector_session is None or self._recognizer_session is None:
                    missing = [
                        str(path)
                        for path in (self._detector_model_path, self._recognizer_model_path)
                        if not path.is_file()
                    ]
                    if missing:
                        raise RecognitionError(
                            "YOLO26 车牌模型不存在或未下载完整: " + ", ".join(missing)
                        )
                    try:
                        import onnxruntime as ort

                        detector = ort.InferenceSession(
                            str(self._detector_model_path),
                            providers=["CPUExecutionProvider"],
                        )
                        recognizer = ort.InferenceSession(
                            str(self._recognizer_model_path),
                            providers=["CPUExecutionProvider"],
                        )
                    except Exception as exc:
                        raise RecognitionError(f"YOLO26 车牌模型加载失败: {exc}") from exc

                    detector_input = detector.get_inputs()[0]
                    detector_shape = detector_input.shape
                    if (
                        len(detector_shape) != 4
                        or not isinstance(detector_shape[2], int)
                        or not isinstance(detector_shape[3], int)
                        or detector_shape[2] != detector_shape[3]
                    ):
                        raise RecognitionError(
                            f"YOLO26 检测模型必须是固定正方形输入，实际为 {detector_shape}"
                        )
                    rec_input = recognizer.get_inputs()[0]
                    rec_shape = rec_input.shape
                    if rec_shape[-2:] != [48, 168] and rec_shape[-2:] != (48, 168):
                        raise RecognitionError(
                            f"YOLO26 识别模型必须使用 48x168 输入，实际为 {rec_shape}"
                        )

                    self._detector_session = detector
                    self._recognizer_session = recognizer
                    self._detector_input_name = detector_input.name
                    self._recognizer_input_name = rec_input.name
                    self._detector_output_name = detector.get_outputs()[0].name
                    output_names = recognizer.get_outputs()
                    if len(output_names) < 2:
                        raise RecognitionError("YOLO26 识别模型必须输出字符和颜色两个结果")
                    self._recognizer_output_names = (output_names[0].name, output_names[1].name)
        return self._detector_session, self._recognizer_session

    def warmup(self) -> None:
        self._get_sessions()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RecognitionError("上传内容不是有效的图片")

        try:
            with self._inference_lock:
                detections = self._detect(image)
                candidates = []
                for detection in detections:
                    try:
                        plate_number, character_confidence = self._recognize_detection(
                            image, detection
                        )
                    except RecognitionError:
                        continue
                    normalized = normalize_plate(plate_number)
                    if not normalized:
                        continue
                    candidates.append(
                        PlateCandidate(
                            plate_number=normalized,
                            confidence=min(detection.box.confidence, character_confidence),
                            box=detection.box,
                        )
                    )
        except RecognitionError:
            raise
        except Exception as exc:
            raise RecognitionError(f"YOLO26 车牌识别失败: {exc}") from exc

        if not detections:
            raise RecognitionError("YOLO26 未检测到车牌，请上传包含清晰车牌的图片")
        if not candidates:
            raise RecognitionError("YOLO26 已定位车牌，但未识别到有效车牌号")
        return max(candidates, key=lambda candidate: candidate.confidence)

    def _detect(self, image: np.ndarray) -> list[_Yolo26Detection]:
        detector_session, _ = self._get_sessions()
        assert self._detector_input_name is not None
        assert self._detector_output_name is not None
        input_shape = detector_session.get_inputs()[0].shape
        input_size = (int(input_shape[2]), int(input_shape[3]))
        tensor, scale, pad_x, pad_y = _preprocess_detector(image, input_size)
        raw = detector_session.run(
            [self._detector_output_name],
            {self._detector_input_name: tensor},
        )[0]
        pred = np.asarray(raw, dtype=np.float32)
        pred = pred[0] if pred.ndim == 3 else pred
        if pred.ndim != 2 or pred.shape[1] < 14:
            raise RecognitionError(f"YOLO26 检测输出格式不支持: {pred.shape}")

        height, width = image.shape[:2]
        detections: list[_Yolo26Detection] = []
        for row in pred:
            confidence = float(row[4])
            if confidence < self._minimum_confidence:
                continue
            plate_type = int(round(float(row[5])))
            if plate_type not in (0, 1):
                continue
            box = _restore_box(row, scale, pad_x, pad_y, width, height)
            landmarks = row[6:14].reshape(4, 2).copy()
            landmarks[:, 0] = (landmarks[:, 0] - pad_x) / scale
            landmarks[:, 1] = (landmarks[:, 1] - pad_y) / scale
            landmarks[:, 0] = np.clip(landmarks[:, 0], 0, width - 1)
            landmarks[:, 1] = np.clip(landmarks[:, 1], 0, height - 1)
            if box.x2 > box.x1 and box.y2 > box.y1:
                detections.append(_Yolo26Detection(box, landmarks, plate_type))
        return sorted(detections, key=lambda detection: detection.box.confidence, reverse=True)

    def _recognize_detection(
        self,
        image: np.ndarray,
        detection: _Yolo26Detection,
    ) -> tuple[str, float]:
        _, recognizer_session = self._get_sessions()
        assert self._recognizer_input_name is not None
        assert self._recognizer_output_names is not None
        roi = _four_point_transform(image, detection.landmarks)
        if detection.plate_type == 1:
            roi = _split_double_line_plate(roi)
        if roi.size == 0:
            raise RecognitionError("YOLO26 车牌透视矫正结果为空")

        tensor = _preprocess_recognizer(roi)
        outputs = recognizer_session.run(
            list(self._recognizer_output_names),
            {self._recognizer_input_name: tensor},
        )
        logits = np.asarray(outputs[0], dtype=np.float32)
        if logits.ndim != 3:
            raise RecognitionError(f"YOLO26 字符识别输出格式不支持: {logits.shape}")
        probabilities = _softmax(logits[0], axis=-1)
        indices = np.argmax(probabilities, axis=-1)
        confidence = np.max(probabilities, axis=-1)

        chars: list[str] = []
        char_confidences: list[float] = []
        previous = 0
        for index, score in zip(indices.tolist(), confidence.tolist()):
            if index != 0 and index != previous and 0 <= index < len(_PLATE_CHARACTERS):
                chars.append(_PLATE_CHARACTERS[index])
                char_confidences.append(float(score))
            previous = index
        if not chars:
            raise RecognitionError("YOLO26 字符识别结果为空")
        return "".join(chars), float(np.mean(char_confidences))


def _preprocess_detector(
    image: np.ndarray, size: tuple[int, int]
) -> tuple[np.ndarray, float, int, int]:
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
    tensor = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.expand_dims(np.ascontiguousarray(tensor), axis=0), scale, left, top


def _preprocess_recognizer(image: np.ndarray) -> np.ndarray:
    resized = cv2.resize(image, (168, 48), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    resized = (resized / 255.0 - 0.588) / 0.193
    tensor = resized.transpose(2, 0, 1)
    return np.expand_dims(np.ascontiguousarray(tensor), axis=0)


def _restore_box(
    row: np.ndarray,
    scale: float,
    pad_x: float,
    pad_y: float,
    width: int,
    height: int,
) -> PlateBox:
    x1 = int(round((float(row[0]) - pad_x) / scale))
    y1 = int(round((float(row[1]) - pad_y) / scale))
    x2 = int(round((float(row[2]) - pad_x) / scale))
    y2 = int(round((float(row[3]) - pad_y) / scale))
    return PlateBox(
        max(0, min(width, x1)),
        max(0, min(height, y1)),
        max(0, min(width, x2)),
        max(0, min(height, y2)),
        max(0.0, min(1.0, float(row[4]))),
    )


def _four_point_transform(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    points = _order_points(landmarks.astype(np.float32))
    (top_left, top_right, bottom_right, bottom_left) = points
    width = max(
        int(np.linalg.norm(bottom_right - bottom_left)),
        int(np.linalg.norm(top_right - top_left)),
    )
    height = max(
        int(np.linalg.norm(top_right - bottom_right)),
        int(np.linalg.norm(top_left - bottom_left)),
    )
    if width < 2 or height < 2:
        return np.empty((0, 0, 3), dtype=image.dtype)
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(points, destination)
    return cv2.warpPerspective(image, matrix, (width, height))


def _order_points(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1)
    ordered[0] = points[np.argmin(sums)]
    ordered[2] = points[np.argmax(sums)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    return ordered


def _split_double_line_plate(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if height < 4 or width < 2:
        return image
    upper = image[0 : int(5 / 12 * height), :]
    lower = image[int(1 / 3 * height) :, :]
    if upper.size == 0 or lower.size == 0:
        return image
    upper = cv2.resize(
        upper,
        (lower.shape[1], lower.shape[0]),
        interpolation=cv2.INTER_LINEAR,
    )
    return np.hstack((upper, lower))


def _softmax(values: np.ndarray, axis: int) -> np.ndarray:
    shifted = values - np.max(values, axis=axis, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=axis, keepdims=True)
