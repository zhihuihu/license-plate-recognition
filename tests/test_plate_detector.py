from pathlib import Path

import cv2
import numpy as np
import pytest

from app.recognizer.plate_detector import YoloV9PlateDetector


MODEL_PATH = Path("models/plate_detector/yolo-v9-t-384-license-plates-end2end.onnx")


@pytest.mark.parametrize("pattern", ["*.jpg", "*.jpeg", "*.png"])
def test_packaged_yolo_detector_finds_plate_regions(pattern):
    if not MODEL_PATH.is_file() or MODEL_PATH.stat().st_size < 1_000_000:
        pytest.skip("Git LFS 模型文件未下载")

    images = sorted(Path("examples").glob(pattern))
    if not images:
        pytest.skip("没有示例图片")

    detector = YoloV9PlateDetector(str(MODEL_PATH), minimum_confidence=0.20)
    for image_path in images:
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        boxes = detector.detect(image)
        assert boxes, image_path
        assert all(box.x1 < box.x2 and box.y1 < box.y2 for box in boxes)
