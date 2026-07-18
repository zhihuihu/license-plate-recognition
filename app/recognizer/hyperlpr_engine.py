from __future__ import annotations

import os
import threading
import zipfile
from pathlib import Path

import cv2
import numpy as np

from .base import PlateCandidate, RecognitionError
from .plate_text import normalize_plate


_MODEL_VERSION = "20230229"
# HyperLPR3 官方 Python 包使用的模型地址目前只提供 HTTP；生产环境建议
# 将模型随镜像一并打包，避免服务运行时下载。
_MODEL_ARCHIVE_URL = f"http://hyperlpr.tunm.top/raw/{_MODEL_VERSION}.zip"
_MODEL_FILES = (
    "onnx/y5fu_320x_sim.onnx",
    "onnx/y5fu_640x_sim.onnx",
    "onnx/rpv3_mdict_160_r3.onnx",
    "onnx/litemodel_cls_96x_r1.onnx",
)


class HyperLprRecognizer:
    """HyperLPR3 适配器，专门用于中国车牌的端到端检测和识别。"""

    def __init__(
        self,
        model_root: str = "models/hyperlpr3",
        detect_level: str = "low",
        allow_model_download: bool = True,
    ) -> None:
        self._model_root = Path(model_root)
        self._detect_level = detect_level.strip().lower()
        self._allow_model_download = allow_model_download
        self._catcher = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    @property
    def model_directory(self) -> Path:
        return self._model_root / ".hyperlpr3" / _MODEL_VERSION

    def _get_catcher(self):
        if self._catcher is None:
            with self._load_lock:
                if self._catcher is None:
                    self._ensure_models()
                    # HyperLPR3 在导入时读取 HOME/HOMEPATH，并且旧版 Windows
                    # 包默认会把相对的 HOMEPATH 拼到根目录。提前指向项目模型目录，
                    # 既避免写入用户目录，也避免服务启动时重复下载模型。
                    model_root = str(self._model_root.resolve())
                    previous_home = os.environ.get("HOME")
                    previous_homepath = os.environ.get("HOMEPATH")
                    os.environ["HOMEPATH"] = model_root
                    os.environ["HOME"] = model_root
                    try:
                        import hyperlpr3 as lpr3

                        level = getattr(lpr3, "DETECT_LEVEL_HIGH", 1)
                        if self._detect_level != "high":
                            level = getattr(lpr3, "DETECT_LEVEL_LOW", 0)
                        self._catcher = lpr3.LicensePlateCatcher(detect_level=level)
                    except ImportError as exc:
                        raise RecognitionError(
                            "HyperLPR3 未安装，请执行 pip install -r requirements.txt"
                        ) from exc
                    except Exception as exc:
                        raise RecognitionError(f"HyperLPR3 模型加载失败: {exc}") from exc
                    finally:
                        if previous_home is None:
                            os.environ.pop("HOME", None)
                        else:
                            os.environ["HOME"] = previous_home
                        if previous_homepath is None:
                            os.environ.pop("HOMEPATH", None)
                        else:
                            os.environ["HOMEPATH"] = previous_homepath
        return self._catcher

    def warmup(self) -> None:
        self._get_catcher()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RecognitionError("上传内容不是有效的图片")

        try:
            with self._inference_lock:
                output = self._get_catcher()(image)
        except RecognitionError:
            raise
        except Exception as exc:
            raise RecognitionError(f"HyperLPR3 识别失败: {exc}") from exc

        candidates = []
        for item in _iter_results(output):
            if len(item) < 2:
                continue
            plate_number = normalize_plate(str(item[0]))
            if not plate_number:
                continue
            try:
                confidence = max(0.0, min(1.0, float(item[1])))
            except (TypeError, ValueError):
                confidence = 0.0
            candidates.append(PlateCandidate(plate_number, confidence))

        if not candidates:
            raise RecognitionError("HyperLPR3 未识别到车牌，请上传更清晰、正对车牌的图片")
        return max(candidates, key=lambda candidate: candidate.confidence)

    def _ensure_models(self) -> None:
        missing = [
            relative_path
            for relative_path in _MODEL_FILES
            if not (self.model_directory / relative_path).is_file()
        ]
        if not missing:
            return

        if not self._allow_model_download:
            raise RecognitionError(
                "离线模式下 HyperLPR3 模型文件不完整，缺少: "
                + ", ".join(missing)
            )

        archive_path = self.model_directory.parent / f"{_MODEL_VERSION}.zip"
        try:
            import requests

            model_directory = self.model_directory
            model_directory.mkdir(parents=True, exist_ok=True)
            response = requests.get(_MODEL_ARCHIVE_URL, timeout=(10, 180))
            response.raise_for_status()
            archive_path.write_bytes(response.content)
            with zipfile.ZipFile(archive_path) as archive:
                _safe_extract(archive, model_directory.parent)
        except Exception as exc:
            raise RecognitionError(
                f"HyperLPR3 模型文件缺失且自动下载失败: {exc}. "
                f"请检查网络，或将 {_MODEL_VERSION} 模型放到 {self.model_directory}"
            ) from exc
        finally:
            if archive_path.is_file():
                try:
                    archive_path.unlink()
                except OSError:
                    pass

        still_missing = [
            relative_path
            for relative_path in _MODEL_FILES
            if not (self.model_directory / relative_path).is_file()
        ]
        if still_missing:
            raise RecognitionError(f"HyperLPR3 模型文件不完整，缺少: {', '.join(still_missing)}")


def _safe_extract(archive: zipfile.ZipFile, target_directory: Path) -> None:
    target_directory = target_directory.resolve()
    for member in archive.infolist():
        destination = (target_directory / member.filename).resolve()
        if destination != target_directory and target_directory not in destination.parents:
            raise RecognitionError("HyperLPR3 模型压缩包包含非法路径")
    archive.extractall(target_directory)


def _iter_results(output: object):
    if output is None:
        return
    if isinstance(output, (list, tuple)):
        for item in output:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[0], str):
                yield item
            elif isinstance(item, (list, tuple)):
                yield from _iter_results(item)
