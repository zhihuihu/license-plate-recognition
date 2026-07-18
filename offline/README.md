# 离线部署资源

该目录面向 Windows x64、CPython 3.13 的无外网环境，包含完整在线服务、PaddleOCR 和 HyperLPR3 的离线依赖 wheel。模型文件位于项目根目录的 `models/`，并通过 Git LFS 管理。

当前资源规模：

- `python-3.13.14-amd64.exe`：Python 3.13.14 x64 官方离线安装包，约 28 MB。
- `wheels/`：84 个 wheel，约 340 MB；包含 PaddlePaddle 3.3.1、PaddleOCR 3.7.0、Paddlex、HyperLPR3、RapidOCR 和全部依赖。
- `../models/`：HyperLPR3 模型约 18 MB；与 PaddleOCR 3.7.0 匹配的 PP-OCRv6 medium/PP-LCNet 模型约 139 MB。
- 目标解释器：Windows x64、CPython 3.13。Linux 或其他 Python ABI 不能直接复用此 wheelhouse。

Python 安装包来自 [Python 3.13.14 官方发布页](https://www.python.org/downloads/release/python-31314/)，SHA256：`c54d9b9bbb8a36e6489363ddd01139707fd781d72f1f9e90c7ec65d0061368e0`。
PaddleOCR 模型选择和版本对应关系以 [PaddleOCR 3.7 模型文档](https://www.paddleocr.ai/v3.7.0/en/version3.x/module_usage/text_detection.html) 为准。

## 取得模型和 wheel

```powershell
git lfs install
git lfs pull
```

执行后确认 `models/hyperlpr3` 和 `models/paddleocr` 下存在模型文件。远程 Git 服务必须启用 Git LFS，并且账号有足够的 LFS 存储和流量额度。

## 无外网安装

目标机器如果没有 Python 3.13 x64，先运行 `offline/python-3.13.14-amd64.exe` 完成安装；安装过程不需要访问 PyPI。然后执行：

```powershell
.\offline\install-offline.ps1
.\offline\verify-offline.ps1
```

脚本默认创建 `.venv-offline`，使用 `offline/wheels` 的本地文件安装 `requirements-paddle.txt`，并验证 PaddleOCR、HyperLPR3 和 RapidOCR 是否可以导入。

## 离线启动

```powershell
$env:OCR_ENGINE = "hyperlpr3"
$env:HYPERLPR_MODEL_ROOT = "models/hyperlpr3"
$env:PADDLEOCR_MODEL_ROOT = "models/paddleocr"
$env:OFFLINE_MODE = "true"
$env:PADDLEOCR_FALLBACK = "true"
$env:RAPIDOCR_FALLBACK = "true"
$env:PRELOAD_OCR_MODEL = "true"

.\.venv-offline\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务启动时会使用本地 HyperLPR3 和 PaddleOCR 模型，不会联网下载。`OFFLINE_MODE=true` 会让 HyperLPR3 在模型缺失时快速失败；PaddleOCR 也会在初始化前检查本地检测、识别和文字行方向模型。如果模型目录不完整，启动日志会提示问题，RapidOCR 仍可作为最终本地兜底。

## 重要限制

- 该 wheelhouse 只适用于 Windows x64 + CPython 3.13；部署到 Linux、ARM 或其他 Python 版本需要重新下载对应平台的 wheel。
- 不要在离线机器上执行普通的 `pip install`，应使用安装脚本的 `--no-index --find-links` 模式。
- 运行环境仍需检查 HyperLPR3、PaddleOCR、PaddlePaddle、RapidOCR 及各模型的许可证和分发条件。
