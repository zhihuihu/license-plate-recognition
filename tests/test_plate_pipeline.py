import cv2
import numpy as np

from app.recognizer.base import PlateBox, PlateCandidate
from app.recognizer.plate_pipeline import DetectedPaddleOcrRecognizer


class FakeDetector:
    def detect(self, image):
        assert image.shape == (100, 200, 3)
        return [PlateBox(20, 30, 120, 70, 0.92)]


class FakeOcr:
    def recognize_image(self, image):
        assert image.shape[0] > 0
        assert image.shape[1] > 0
        return PlateCandidate("苏A8K2N6", 0.96)


def test_detected_paddleocr_returns_detection_box():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success

    recognizer = DetectedPaddleOcrRecognizer(FakeDetector(), FakeOcr())
    result = recognizer.recognize(encoded.tobytes())

    assert result.plate_number == "苏A8K2N6"
    assert result.box == PlateBox(20, 30, 120, 70, 0.92)
    assert result.confidence == 0.92
