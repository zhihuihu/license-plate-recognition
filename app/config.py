from __future__ import annotations

import os
from dataclasses import dataclass


API_PREFIX = "/os/inter-api/lpr"


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


@dataclass(frozen=True, slots=True)
class Settings:
    ocr_engine: str = os.getenv("OCR_ENGINE", "hyperlpr3").strip().lower()
    hyperlpr_model_root: str = os.getenv("HYPERLPR_MODEL_ROOT", "models/hyperlpr3")
    hyperlpr_detect_level: str = os.getenv("HYPERLPR_DETECT_LEVEL", "low").strip().lower()
    hyperlpr_min_confidence: float = float(os.getenv("HYPERLPR_MIN_CONFIDENCE", "0.80"))
    offline_mode: bool = _bool_env("OFFLINE_MODE", False)
    paddleocr_fallback: bool = _bool_env("PADDLEOCR_FALLBACK", True)
    paddleocr_min_confidence: float = float(os.getenv("PADDLEOCR_MIN_CONFIDENCE", "0.80"))
    paddleocr_model_root: str = os.getenv("PADDLEOCR_MODEL_ROOT", "models/paddleocr")
    rapidocr_fallback: bool = _bool_env("RAPIDOCR_FALLBACK", True)
    max_upload_bytes: int = _int_env("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    # 接收并排队至少 10 个同时到达的识别请求；OCR 引擎自身仍可能
    # 因线程安全锁而串行推理，实际吞吐需要通过压测确认。
    max_concurrent_requests: int = _int_env("MAX_CONCURRENT_REQUESTS", 10)
    # 每个实例各自持有一套 OCR/ONNX 推理对象，实例之间可以并行推理。
    ocr_instance_count: int = _int_env("OCR_INSTANCE_COUNT", 1)
    # 请求在识别槽位前最多等待 30 秒。超时返回 503，而不是把正常的
    # 瞬时排队当成 429 Too Many Requests。
    inference_queue_timeout_ms: int = _int_env("INFERENCE_QUEUE_TIMEOUT_MS", 30000)
    preload_ocr_model: bool = _bool_env("PRELOAD_OCR_MODEL", True)
    api_keys: tuple[str, ...] = tuple(
        key.strip()
        for key in os.getenv("API_KEYS", "").split(",")
        if key.strip()
    )
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    )


settings = Settings()
