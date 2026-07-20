from pathlib import Path

import pytest

from app.recognizer.yolo26_engine import Yolo26PlateRecognizer, _split_double_line_plate


DETECTOR_MODEL = Path("models/plate_detector/yolo26s-plate-detect.onnx")
RECOGNIZER_MODEL = Path("models/plate_detector/plate_rec_color.onnx")


@pytest.mark.parametrize(
    ("image_name", "expected"),
    [("车牌.jpg", "浙AX7U36"), ("车牌2.jpeg", "WJN22628")],
)
def test_packaged_yolo26_recognizes_examples(image_name, expected):
    if not DETECTOR_MODEL.is_file() or not RECOGNIZER_MODEL.is_file():
        pytest.skip("Git LFS YOLO26 模型文件未下载")
    image_path = Path("examples") / image_name
    if not image_path.is_file():
        pytest.skip(f"示例图片不存在: {image_path}")

    recognizer = Yolo26PlateRecognizer(str(DETECTOR_MODEL), str(RECOGNIZER_MODEL))
    result = recognizer.recognize(image_path.read_bytes())

    assert result.plate_number == expected
    assert result.box is not None
    assert result.box.x1 < result.box.x2
    assert result.box.y1 < result.box.y2


def test_double_line_plate_split_keeps_two_rows():
    import numpy as np

    image = np.zeros((120, 240, 3), dtype=np.uint8)
    merged = _split_double_line_plate(image)

    assert merged.shape[0] > 0
    assert merged.shape[1] == 480
