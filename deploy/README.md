# Docker 部署

镜像由 GitHub Actions 构建并推送到 GitHub Container Registry（GHCR）。镜像内已经包含 HyperLPR3、PaddleOCR 和 RapidOCR 模型，部署机运行时不需要访问外网，也不需要挂载模型目录。

环境变量的完整说明见 [../docs/configuration.md](../docs/configuration.md)。本文件重点说明镜像获取、离线导入和 Docker 启动方式。

## GitHub 构建

`.github/workflows/docker-image1.yml` 负责构建并发布镜像。将代码和 Git LFS 对象推送到 GitHub 后，工作流会：

1. 拉取真实模型文件，而不是 LFS pointer 文件。
2. 使用 Linux x86_64、Python 3.13 构建镜像。
3. 执行 Dockerfile 中的模型完整性检查。
4. 将镜像推送到 `ghcr.io/zhihuihu/license-plate-recognition`，并生成 `latest`、分支、tag、commit SHA 标签。

工作流使用 `GITHUB_TOKEN` 登录 GHCR，并声明 `packages: write` 权限。GitHub 官方文档说明，工作流发布仓库关联的 Container Registry 包可以使用该 Token。

当前工作流只会在推送版本 Tag 或手动执行时运行：

- 推送 `v1.2.3`：生成 `:v1.2.3` 和 `:sha-提交短哈希` 镜像。
- 手动执行：默认生成 `:manual` 和 `:sha-提交短哈希`，也可以在 `image_tag` 输入框中填写自定义标签。
- 从默认分支手动执行时，还会生成 `:latest`；普通分支推送不会触发构建。

## 在有外网的机器准备镜像

```bash
IMAGE=ghcr.io/zhihuihu/license-plate-recognition:latest
echo "$GHCR_TOKEN" | docker login ghcr.io -u GITHUB_USERNAME --password-stdin
docker pull "$IMAGE"
docker save "$IMAGE" -o license-plate-recognition.tar
```

将 `license-plate-recognition.tar` 复制到无外网的 Docker 主机后：

```bash
docker load -i license-plate-recognition.tar
```

Compose 已设置 `pull_policy: never`，离线主机只会使用本地已加载的镜像，不会在启动时尝试访问 GHCR。

如果目标环境是 Linux ARM64，当前工作流的 `linux/amd64` 镜像不能直接使用，需要另建 ARM64 兼容的 PaddlePaddle wheel 和镜像平台。

## 使用 Docker Compose 启动

在 `deploy/` 目录执行：

```powershell
Copy-Item .env.docker.example .env
# 编辑 .env，填写 API_KEYS
docker compose up -d
docker compose ps
docker compose logs -f lpr
```

浏览器打开 <http://localhost:8000/os/inter-api/lpr/ui/> 即可手动上传图片识别车牌。页面与 API 共用同一个容器，不需要额外部署前端服务。

验证探针和识别接口：

```powershell
Invoke-WebRequest http://localhost:8000/os/inter-api/lpr/readyz
curl.exe -X POST http://localhost:8000/os/inter-api/lpr/recognitions `
  -F "file=@../examples/车牌.jpg"
```

升级镜像：

```powershell
docker compose pull
docker compose up -d
```

Compose 默认启用只读根文件系统、丢弃 Linux capabilities、禁止提权，并将临时写入放到 `/tmp`。如果宿主机安全策略不允许 `read_only` 或 `tmpfs`，需要保留这些约束并针对宿主机调整，而不是直接依赖容器写入模型目录。

## 常见启动错误

如果日志出现 `ImportError: libGL.so.1: cannot open shared object file`，说明使用的仍是旧镜像或旧缓存层。当前 Dockerfile 会移除 GUI 版 OpenCV，只保留 `opencv-python-headless`，并在构建阶段执行 `import cv2` 自检。

推送新代码后，在有外网的机器重新拉取镜像，再重新导出给无外网环境：

```bash
docker pull ghcr.io/zhihuihu/license-plate-recognition:latest
docker save ghcr.io/zhihuihu/license-plate-recognition:latest -o license-plate-recognition.tar
```
