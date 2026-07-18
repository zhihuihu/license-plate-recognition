from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as module
import app.security as security
from app.config import API_PREFIX
from app.recognizer.fallback import FallbackRecognizer
from app.recognizer.base import PlateCandidate, RecognitionError
from app.recognizer.paddleocr_engine import PaddleOcrRecognizer, _iter_text_scores


class FakeRecognizer:
    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        assert image_bytes == b"fake-image"
        return PlateCandidate("苏A8K2N6", 0.9876)


def test_health_and_recognition_contract(monkeypatch):
    monkeypatch.setattr(module.recognition_service, "_recognizer", FakeRecognizer())
    with TestClient(module.app) as client:
        assert client.get(f"{API_PREFIX}/livez").json() == {
            "code": 0,
            "message": "success",
            "data": {"status": "ok"},
        }
        assert client.get(f"{API_PREFIX}/healthz").json() == {
            "code": 0,
            "message": "success",
            "data": {"status": "ok"},
        }
        assert client.get(f"{API_PREFIX}/readyz").status_code == 200
        assert client.get(f"{API_PREFIX}/startupz").json() == {
            "code": 0,
            "message": "success",
            "data": {"status": "started"},
        }
        assert client.get("/health").status_code == 404

        response = client.post(
            f"{API_PREFIX}/recognitions",
            headers={"X-Request-ID": "test-request-001"},
            files={"file": ("plate.jpg", b"fake-image", "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    assert body["data"]["request_id"] == "test-request-001"
    assert body["data"]["plate_number"] == "苏A8K2N6"
    assert body["data"]["confidence"] == 0.9876
    assert body["data"]["processing_time_ms"] >= 0
    assert body["data"]["recognized_at"].endswith("Z")
    assert response.headers["X-Request-ID"] == "test-request-001"


def test_manual_recognition_ui_is_available(monkeypatch):
    monkeypatch.setattr(module.recognition_service, "_recognizer", FakeRecognizer())
    with TestClient(module.app) as client:
        response = client.get(f"{API_PREFIX}/ui/")

    assert response.status_code == 200
    assert "车牌识别终端" in response.text
    assert "开始识别" in response.text


def test_invalid_file_returns_structured_error(monkeypatch):
    monkeypatch.setattr(module.recognition_service, "_recognizer", FakeRecognizer())
    with TestClient(module.app) as client:
        response = client.post(
            f"{API_PREFIX}/recognitions",
            files={"file": ("notes.txt", b"text", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert response.json()["message"] == "只支持上传图片文件"
    assert response.json()["data"]["error_code"] == "INVALID_REQUEST"
    assert response.json()["data"]["request_id"]


def test_api_key_is_required_when_configured(monkeypatch):
    monkeypatch.setattr(module.recognition_service, "_recognizer", FakeRecognizer())
    monkeypatch.setattr(security, "settings", type("Settings", (), {"api_keys": ("test-secret",)})())

    with TestClient(module.app) as client:
        assert client.post(
            f"{API_PREFIX}/recognitions",
            files={"file": ("plate.jpg", b"fake-image", "image/jpeg")},
        ).status_code == 401
        assert client.post(
            f"{API_PREFIX}/recognitions",
            headers={"X-API-Key": "wrong"},
            files={"file": ("plate.jpg", b"fake-image", "image/jpeg")},
        ).status_code == 403
        assert client.post(
            f"{API_PREFIX}/recognitions",
            headers={"X-API-Key": "test-secret"},
            files={"file": ("plate.jpg", b"fake-image", "image/jpeg")},
        ).status_code == 200


def test_low_confidence_primary_uses_local_fallback():
    class Primary:
        def recognize(self, _: bytes) -> PlateCandidate:
            return PlateCandidate("苏JJ77JCJ", 0.2)

    class Fallback:
        def recognize(self, _: bytes) -> PlateCandidate:
            return PlateCandidate("浙AX7U36", 0.99)

    result = FallbackRecognizer(Primary(), Fallback()).recognize(b"image")
    assert result.plate_number == "浙AX7U36"
    assert result.confidence == 0.99


def test_paddleocr_v3_output_is_parsed():
    output = {
        "rec_texts": ["浙 A·X7U36", "停车场"],
        "rec_scores": [0.96, 0.88],
    }

    assert list(_iter_text_scores(output)) == [
        ("浙 A·X7U36", 0.96),
        ("停车场", 0.88),
    ]


def test_paddleocr_v2_output_is_parsed():
    output = [[[[0, 0], [10, 0], [10, 10], [0, 10]], ("浙AX7U36", 0.97)]]

    assert list(_iter_text_scores(output)) == [("浙AX7U36", 0.97)]


def test_paddleocr_uses_local_v6_model_directories():
    recognizer = PaddleOcrRecognizer("models/paddleocr")

    assert recognizer._det_model_dir.endswith("PP-OCRv6_medium_det_infer")
    assert recognizer._rec_model_dir.endswith("PP-OCRv6_medium_rec_infer")
    assert recognizer._textline_model_dir.endswith("PP-LCNet_x1_0_textline_ori_infer")


def test_paddleocr_fails_fast_when_local_models_are_missing(tmp_path):
    with pytest.raises(RecognitionError, match="本地模型文件不完整"):
        PaddleOcrRecognizer(str(tmp_path)).warmup()
