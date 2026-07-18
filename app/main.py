from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import API_PREFIX, settings
from .errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .middleware import RequestContextMiddleware
from .recognizer import (
    FallbackRecognizer,
    HyperLprRecognizer,
    PaddleOcrRecognizer,
    RapidOcrRecognizer,
    RecognitionError,
    RecognizerPool,
)
from .security import require_api_key
from .schemas import ApiResponse, ErrorResponse, RecognitionResponse
from .service import RecognitionService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("license_plate.app")


def _create_recognizer():
    if settings.ocr_engine in {"hyperlpr3", "hyperlpr"}:
        primary = HyperLprRecognizer(
            model_root=settings.hyperlpr_model_root,
            detect_level=settings.hyperlpr_detect_level,
            allow_model_download=not settings.offline_mode,
        )
        fallback = None
        if settings.rapidocr_fallback:
            fallback = RapidOcrRecognizer()
        if settings.paddleocr_fallback:
            fallback = FallbackRecognizer(
                PaddleOcrRecognizer(model_root=settings.paddleocr_model_root),
                fallback or RapidOcrRecognizer(),
                minimum_confidence=settings.paddleocr_min_confidence,
            )
        if fallback is not None:
            return FallbackRecognizer(
                primary,
                fallback,
                minimum_confidence=settings.hyperlpr_min_confidence,
            )
        return primary
    if settings.ocr_engine == "rapidocr":
        return RapidOcrRecognizer()
    raise ValueError(f"不支持的 OCR_ENGINE: {settings.ocr_engine}")


recognizer_pool = RecognizerPool(_create_recognizer, settings.ocr_instance_count)
recognition_service = RecognitionService(recognizer_pool)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.inference_slots = asyncio.Semaphore(settings.max_concurrent_requests)
    app.state.ocr_ready = False
    app.state.startup_complete = False
    logger.info(
        "ocr_pool_initialized instances=%s max_concurrent_requests=%s",
        recognizer_pool.size,
        settings.max_concurrent_requests,
    )
    if settings.preload_ocr_model:
        try:
            await run_in_threadpool(recognition_service.warmup)
            app.state.ocr_ready = True
        except RecognitionError:
            logger.exception("ocr_warmup_failed")
            raise
    else:
        # 关闭预热时，模型会在首个请求时懒加载；进程本身已经可以接收请求。
        app.state.ocr_ready = True
    app.state.startup_complete = True
    yield


app = FastAPI(
    title="车牌识别服务",
    description="上传停车场车辆图片，返回车牌号、识别时间、处理耗时和置信度。",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

UI_PATH = f"{API_PREFIX}/ui"
app.mount(
    UI_PATH,
    StaticFiles(directory=Path(__file__).with_name("web"), html=True),
    name="lpr-ui",
)


@app.get(UI_PATH, include_in_schema=False)
def ui_root() -> RedirectResponse:
    """将不带斜杠的页面地址重定向到静态首页。"""
    return RedirectResponse(url=f"{UI_PATH}/", status_code=307)


@app.get(
    f"{API_PREFIX}/livez",
    tags=["system"],
    summary="Kubernetes 存活探针",
)
@app.get(
    f"{API_PREFIX}/healthz",
    tags=["system"],
    include_in_schema=False,
)
def livez() -> ApiResponse[dict[str, str]]:
    """只检查进程是否能响应，不检查模型，避免活跃实例被误杀。"""
    return ApiResponse(code=0, message="success", data={"status": "ok"})


@app.get(
    f"{API_PREFIX}/readyz",
    tags=["system"],
    summary="Kubernetes 就绪探针",
)
def readyz(request: Request) -> ApiResponse[dict[str, str]]:
    if not getattr(request.app.state, "ocr_ready", False):
        raise HTTPException(status_code=503, detail="OCR 引擎尚未就绪")
    return ApiResponse(
        code=0,
        message="success",
        data={"status": "ready", "ocr_engine": settings.ocr_engine},
    )


@app.get(
    f"{API_PREFIX}/startupz",
    tags=["system"],
    summary="Kubernetes 启动探针",
)
def startupz(request: Request) -> ApiResponse[dict[str, str]]:
    if not getattr(request.app.state, "startup_complete", False):
        raise HTTPException(status_code=503, detail="服务仍在启动")
    return ApiResponse(code=0, message="success", data={"status": "started"})


@app.post(
    f"{API_PREFIX}/recognitions",
    response_model=ApiResponse[RecognitionResponse],
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["recognition"],
    summary="识别一张车牌图片",
)
async def recognize_plate(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
) -> ApiResponse[RecognitionResponse]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持上传图片文件")

    # 先等待识别槽位，再把上传内容复制到内存，避免大量排队请求同时
    # 持有完整图片字节；UploadFile 本身由 FastAPI 负责生命周期管理。
    slots = request.app.state.inference_slots
    acquired = False
    try:
        await asyncio.wait_for(
            slots.acquire(),
            timeout=settings.inference_queue_timeout_ms / 1000,
        )
        acquired = True

        image_bytes = await file.read(settings.max_upload_bytes + 1)
        if len(image_bytes) > settings.max_upload_bytes:
            max_mb = round(settings.max_upload_bytes / 1024 / 1024, 2)
            raise HTTPException(status_code=413, detail=f"图片大小不能超过 {max_mb} MB")
        if not image_bytes:
            raise HTTPException(status_code=400, detail="上传的图片不能为空")

        result = await run_in_threadpool(
            recognition_service.recognize,
            image_bytes,
            request.state.request_id,
        )
        return ApiResponse(code=0, message="success", data=result)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail="识别队列等待超时，请稍后重试",
            headers={"Retry-After": "1"},
        ) from exc
    except RecognitionError as exc:
        message = str(exc)
        status_code = 503 if "未安装" in message or "加载失败" in message else 422
        raise HTTPException(status_code=status_code, detail=message) from exc
    finally:
        if acquired:
            slots.release()
