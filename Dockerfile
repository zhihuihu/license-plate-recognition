# syntax=docker/dockerfile:1.7

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    OCR_ENGINE=hyperlpr3 \
    HYPERLPR_MODEL_ROOT=/app/models/hyperlpr3 \
    PADDLEOCR_MODEL_ROOT=/app/models/paddleocr \
    PLATE_DETECTOR_MODEL_PATH=/app/models/plate_detector/yolo-v9-t-384-license-plates-end2end.onnx \
    PLATE_DETECTOR_MIN_CONFIDENCE=0.40 \
    PLATE_DETECTOR_PADDING_RATIO=0.08 \
    YOLO26_DETECTOR_MODEL_PATH=/app/models/plate_detector/yolo26s-plate-detect.onnx \
    YOLO26_RECOGNIZER_MODEL_PATH=/app/models/plate_detector/plate_rec_color.onnx \
    YOLO26_MIN_CONFIDENCE=0.20 \
    OFFLINE_MODE=true \
    PADDLEOCR_FALLBACK=true \
    RAPIDOCR_FALLBACK=true \
    PRELOAD_OCR_MODEL=true \
    MAX_CONCURRENT_REQUESTS=10 \
    OCR_INSTANCE_COUNT=1 \
    INFERENCE_QUEUE_TIMEOUT_MS=30000

WORKDIR /app

COPY requirements.txt requirements-docker.txt ./

# PaddleOCR may pull a GUI-enabled OpenCV package as a transitive dependency.
# Keep only the headless build because this service never opens a desktop window.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-docker.txt \
    && pip uninstall --yes opencv-python opencv-contrib-python \
    && pip install --no-cache-dir --no-deps --force-reinstall "opencv-python-headless>=4.10,<5" \
    && python -c "import cv2; print('OpenCV loaded:', cv2.__version__)"

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /tmp/.cache \
    && chown -R appuser:appuser /tmp

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser models ./models

# Fail the image build if Git LFS pointers or incomplete model directories
# were copied instead of the real model files.
RUN python - <<'PY'
from pathlib import Path

required = {
    "models/hyperlpr3/.hyperlpr3/20230229/onnx/y5fu_320x_sim.onnx": 1_000_000,
    "models/hyperlpr3/.hyperlpr3/20230229/onnx/y5fu_640x_sim.onnx": 1_000_000,
    "models/hyperlpr3/.hyperlpr3/20230229/onnx/rpv3_mdict_160_r3.onnx": 1_000_000,
    "models/hyperlpr3/.hyperlpr3/20230229/onnx/litemodel_cls_96x_r1.onnx": 1_000_000,
    "models/paddleocr/PP-OCRv6_medium_det_infer/inference.json": 1,
    "models/paddleocr/PP-OCRv6_medium_det_infer/inference.pdiparams": 1_000_000,
    "models/paddleocr/PP-OCRv6_medium_det_infer/inference.yml": 1,
    "models/paddleocr/PP-OCRv6_medium_rec_infer/inference.json": 1,
    "models/paddleocr/PP-OCRv6_medium_rec_infer/inference.pdiparams": 1_000_000,
    "models/paddleocr/PP-OCRv6_medium_rec_infer/inference.yml": 1,
    "models/paddleocr/PP-LCNet_x1_0_textline_ori_infer/inference.json": 1,
    "models/paddleocr/PP-LCNet_x1_0_textline_ori_infer/inference.pdiparams": 1_000_000,
    "models/paddleocr/PP-LCNet_x1_0_textline_ori_infer/inference.yml": 1,
    "models/plate_detector/yolo-v9-t-384-license-plates-end2end.onnx": 1_000_000,
    "models/plate_detector/yolo26s-plate-detect.onnx": 10_000_000,
    "models/plate_detector/plate_rec_color.onnx": 500_000,
}

missing = []
for relative_path, minimum_size in required.items():
    path = Path(relative_path)
    if not path.is_file() or path.stat().st_size < minimum_size:
        missing.append(f"{path} (< {minimum_size} bytes)")
if missing:
    raise SystemExit("Incomplete or missing model files:\n" + "\n".join(missing))
PY

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8000/os/inter-api/lpr/readyz', timeout=3); raise SystemExit(0 if response.status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
