# 车牌识别服务

面向停车场场景的本地车牌识别服务。上传车辆图片后，返回标准化车牌号、识别完成时间、服务端处理耗时、置信度和请求编号。

项目整体按 AGPL-3.0 发布；`yolo26` 识别链路集成并修改了 [we0091234/yolo26-plate](https://github.com/we0091234/yolo26-plate) 的模型推理思路，第三方来源和模型转换信息见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

服务运行在自己的机器或 Docker 容器中，图片不会发送到远程识别接口。项目默认使用 HyperLPR3 主识别，低置信度时使用 PaddleOCR 复核，最后使用 RapidOCR 本地兜底。

## 能做什么

- 提供图片上传识别 API 和浏览器手动识别页面
- 支持中国常见蓝牌、黄牌、新能源车牌及部分特殊牌型清洗
- 尝试处理常见双层车牌和摩托车双层车牌
- 返回车牌号、识别时间、服务端耗时、置信度和请求 ID
- 统一 `code`、`message`、`data` 响应格式
- 提供 Kubernetes 存活、就绪、启动探针
- 支持 API Key 鉴权、请求排队、多 OCR 实例和离线 Docker 部署
- 预留识别引擎适配器，后续可以接入单独训练的模型
- 车牌类型、特殊牌型和不保证场景见 [docs/plate-types.md](docs/plate-types.md)

这是“单张图片识别服务”，不是完整的停车场收费系统。车辆进出事件、摄像头接入、去重、黑白名单和收费业务应在后续业务层扩展。

## 最快启动：使用 Docker 镜像

GitHub Actions 会把镜像发布到：

```text
ghcr.io/zhihuihu/license-plate-recognition:latest
```

镜像已经包含运行时、OCR 依赖和模型文件，部署机运行时不需要访问外网，也不需要挂载 `models/`。当前镜像目标平台为 `linux/amd64`。

### 1. 准备镜像

有外网的 Docker 主机：

```bash
export IMAGE=ghcr.io/zhihuihu/license-plate-recognition:latest
echo "$GHCR_TOKEN" | docker login ghcr.io -u GITHUB_USERNAME --password-stdin
docker pull "$IMAGE"
```

私有 GHCR 镜像需要具备 `read:packages` 权限的 Token；公开镜像可以直接拉取。

无外网主机请在有外网机器执行 `docker save`，再将文件复制到目标主机执行 `docker load`，详见 [deploy/README.md](deploy/README.md)。

### 2. 配置并启动 Compose

```powershell
Set-Location deploy
Copy-Item .env.docker.example .env
# 编辑 .env，至少替换 API_KEYS
docker compose up -d
docker compose ps
```

Linux/macOS 可以执行：

```bash
cd deploy
cp .env.docker.example .env
# 编辑 .env，至少替换 API_KEYS
docker compose up -d
```

访问：

- 手动识别页面：<http://localhost:8000/os/inter-api/lpr/ui/>
- 就绪检查：<http://localhost:8000/os/inter-api/lpr/readyz>
- 接口文档：<http://localhost:8000/os/inter-api/lpr/docs>

完整的 GHCR、单容器、Compose 安全参数和离线导入流程见 [deploy/README.md](deploy/README.md)。

## 环境变量快速说明

配置文件模板：[deploy/.env.docker.example](deploy/.env.docker.example)。完整说明见 [docs/configuration.md](docs/configuration.md)。

| 变量 | 常用值 | 作用 |
| --- | --- | --- |
| `API_KEYS` | 随机长密钥 | 生产环境接口鉴权，多个密钥用逗号分隔 |
| `OCR_ENGINE` | `hyperlpr3` | 主识别引擎，可选 `hyperlpr3`、`paddleocr`、`yolo26`、`rapidocr`；`yolo26` 使用中国车牌专用 Pose 检测和识别模型 |
| `OFFLINE_MODE` | `true` | Docker/无外网环境禁止联网下载模型 |
| `PADDLEOCR_FALLBACK` | `true` | 是否启用 PaddleOCR 复核 |
| `RAPIDOCR_FALLBACK` | `true` | 是否启用 RapidOCR 兜底 |
| `MAX_CONCURRENT_REQUESTS` | `10` | 最大排队请求数量，不等于每秒吞吐量 |
| `OCR_INSTANCE_COUNT` | `1`～`2` | OCR 独立实例数量，需要按压测和内存调整 |
| `INFERENCE_QUEUE_TIMEOUT_MS` | `30000` | 排队超时后返回 503，不返回 429 |
| `PLATE_DETECTOR_MODEL_PATH` | `models/plate_detector/yolo-v9-t-384-license-plates-end2end.onnx` | `paddleocr` 模式使用的 YOLO 车牌检测模型路径 |
| `PLATE_DETECTOR_MIN_CONFIDENCE` | `0.40` | `paddleocr` 模式下 YOLO 车牌检测最低置信度 |
| `PLATE_DETECTOR_PADDING_RATIO` | `0.08` | 车牌框裁剪时四周扩展比例 |
| `YOLO26_DETECTOR_MODEL_PATH` | `models/plate_detector/yolo26s-plate-detect.onnx` | `yolo26` 模式的 Pose 检测模型路径 |
| `YOLO26_RECOGNIZER_MODEL_PATH` | `models/plate_detector/plate_rec_color.onnx` | `yolo26` 模式的专用字符识别模型路径 |
| `YOLO26_MIN_CONFIDENCE` | `0.20` | `yolo26` 车牌检测最低置信度 |
| `LPR_IMAGE` | GHCR 镜像地址 | Compose 使用的镜像地址 |
| `LPR_PORT` | `8000` | 宿主机访问端口 |

生产环境至少修改 `API_KEYS`。Docker 镜像内的模型路径由容器固定，不要将 `HYPERLPR_MODEL_ROOT` 或 `PADDLEOCR_MODEL_ROOT` 改成宿主机路径。

## API 快速示例

```bash
curl.exe -X POST http://localhost:8000/os/inter-api/lpr/recognitions -H "X-API-Key: replace-with-a-long-random-key" -F "file=@examples/车牌.jpg"
```

成功响应的顶层结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "plate_number": "浙AX7U36",
    "recognized_at": "2026-07-17T06:49:39.182995Z",
    "processing_time_ms": 151.4,
    "confidence": 0.9999,
    "plate_box": {
      "x1": 120,
      "y1": 240,
      "x2": 420,
      "y2": 315,
      "confidence": 0.96
    },
    "request_id": "..."
  }
}
```

完整请求参数、错误码和 Kubernetes 探针见 [docs/api.md](docs/api.md)。

## 后续扩展方向

- 接入摄像头视频流和多帧投票，提高夜间、逆光和运动模糊场景稳定性
- 增加车辆进出事件、车道、相机和去重状态机
- 对接黑名单、白名单、收费系统和停车场业务平台
- 增加 Prometheus 指标、审计日志和异常告警
- 单独创建训练项目，使用现场数据微调检测和识别模型
- 通过 `app/recognizer/` 适配器接入新模型，不把训练代码混入在线服务

开发、测试、识别器扩展和自研模型训练说明见 [docs/development.md](docs/development.md)。

## 项目结构

```text
app/                         在线服务、识别引擎和内置页面
tests/                       API 和识别适配器测试
models/                      HyperLPR3/PaddleOCR/YOLO26 模型，使用 Git LFS
deploy/                      Docker Compose、GHCR 和离线导入说明
offline/                     Windows x64 / Python 3.13 离线资源
docs/                        配置、API、开发和扩展文档
.github/workflows/           GitHub Actions 镜像构建工作流
Dockerfile                   包含模型的 linux/amd64 镜像构建文件
```

## 其他文档

- [Docker 部署](deploy/README.md)
- [环境变量配置](docs/configuration.md)
- [API、页面和健康探针](docs/api.md)
- [车牌类型与识别边界](docs/plate-types.md)
- [开发、扩展和自研训练](docs/development.md)
- [Windows 无外网部署](offline/README.md)

## 商用前检查

- 配置强随机 `API_KEYS`，不要提交 `.env`
- 使用目标停车场的独立图片集验收识别率和 P95 延迟
- 核对 HyperLPR3、PaddleOCR、PaddlePaddle、RapidOCR 和模型许可证
- 对上传图片制定访问控制、保留期限、脱敏和审计策略
