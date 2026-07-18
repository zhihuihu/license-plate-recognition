# 配置说明

服务通过环境变量配置。Windows 本地运行可以使用 `.env` 配合 Uvicorn，Docker Compose 使用 `deploy/.env`，单容器使用 `--env-file`。

## 配置文件用法

### Windows 本地运行

```powershell
Copy-Item .env.example .env
# 编辑 .env 后执行
uvicorn --env-file .env app.main:app --host 0.0.0.0 --port 8000
```

### Docker Compose

```powershell
Set-Location deploy
Copy-Item .env.docker.example .env
# 编辑 .env 后执行
docker compose up -d
```

`deploy/.env` 中的 `LPR_IMAGE` 和 `LPR_PORT` 用于 Compose 文件插值，其余变量通过 `env_file` 传入服务容器。

### 单容器

```bash
docker run --env-file deploy/.env.docker -p 8000:8000 ghcr.io/zhihuihu/license-plate-recognition:latest
```

## 服务变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `API_KEYS` | 空 | 逗号分隔的接口密钥。生产环境必须配置；请求通过 `X-API-Key` 传入。 |
| `OCR_ENGINE` | `hyperlpr3` | 主引擎，可选 `hyperlpr3` 或 `rapidocr`。 |
| `OFFLINE_MODE` | `false` | `true` 时禁止模型联网下载。Docker 和无外网环境应保持为 `true`。 |
| `PADDLEOCR_FALLBACK` | `true` | 是否启用 PaddleOCR 复核。 |
| `RAPIDOCR_FALLBACK` | `true` | 是否启用 RapidOCR 最终兜底。 |
| `PRELOAD_OCR_MODEL` | `true` | 启动时预热模型；生产环境建议开启。 |
| `HYPERLPR_MODEL_ROOT` | `models/hyperlpr3` | HyperLPR3 模型目录。Docker 内固定为 `/app/models/hyperlpr3`。 |
| `PADDLEOCR_MODEL_ROOT` | `models/paddleocr` | PaddleOCR 模型目录。Docker 内固定为 `/app/models/paddleocr`。 |
| `HYPERLPR_DETECT_LEVEL` | `low` | `low` 速度优先；`high` 适合远距离小车牌。 |
| `HYPERLPR_MIN_CONFIDENCE` | `0.80` | HyperLPR3 低于该值时进入复核链路。 |
| `PADDLEOCR_MIN_CONFIDENCE` | `0.80` | PaddleOCR 低于该值时继续回退。 |
| `MAX_UPLOAD_BYTES` | `10485760` | 单张图片最大字节数，默认 10 MB。 |
| `MAX_CONCURRENT_REQUESTS` | `10` | 可进入识别服务并排队的请求数量，不等于每秒吞吐量。 |
| `OCR_INSTANCE_COUNT` | `1` | 独立 OCR 实例数量。每增加一个实例都会增加模型内存，应通过压测调整。 |
| `INFERENCE_QUEUE_TIMEOUT_MS` | `30000` | 请求最长排队时间。超时返回 HTTP 503，不返回 429。 |
| `ALLOWED_ORIGINS` | `*` | CORS 来源，多个来源用逗号分隔。内置页面和 API 同源访问不需要配置。 |

## Docker 专用变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LPR_IMAGE` | 无 | Compose 使用的镜像地址，默认项目镜像为 `ghcr.io/zhihuihu/license-plate-recognition:latest`。 |
| `LPR_PORT` | `8000` | 宿主机端口，容器内部端口固定为 `8000`。 |

Docker 镜像已经内置模型，运行时不需要挂载 `models/`。Compose 会固定以下容器内部路径和缓存目录，不建议修改：

```text
HYPERLPR_MODEL_ROOT=/app/models/hyperlpr3
PADDLEOCR_MODEL_ROOT=/app/models/paddleocr
HOME=/tmp
XDG_CACHE_HOME=/tmp/.cache
```

## 推荐配置

### 生产环境

```dotenv
API_KEYS=replace-with-a-long-random-key
OCR_ENGINE=hyperlpr3
OFFLINE_MODE=true
PADDLEOCR_FALLBACK=true
RAPIDOCR_FALLBACK=true
PRELOAD_OCR_MODEL=true
MAX_CONCURRENT_REQUESTS=10
OCR_INSTANCE_COUNT=1
INFERENCE_QUEUE_TIMEOUT_MS=30000
```

### 多实例调优

建议固定 `MAX_CONCURRENT_REQUESTS=10`，分别测试 `OCR_INSTANCE_COUNT=1`、`2`、`3`、`4`，同时观察吞吐率、P95 延迟和内存。实例越多不一定越快，ONNX Runtime 线程竞争可能导致吞吐下降。

更完整的 Docker 拉取、离线导入和 Compose 安全配置见 [../deploy/README.md](../deploy/README.md)。
