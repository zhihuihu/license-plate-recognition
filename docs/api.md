# API 与页面

所有接口使用统一前缀：

```text
/os/inter-api/lpr
```

## 手动识别页面

浏览器打开：

<http://localhost:8000/os/inter-api/lpr/ui/>

页面支持点击选择、拖拽、手机拍照和粘贴图片，显示车牌号、识别完成时间、服务端耗时、客户端耗时、置信度和请求编号。

如果配置了 `API_KEYS`，在页面的接口密钥输入框中填写密钥即可。密钥只保存在当前页面内存中。

## 识别接口

### 请求

```bash
curl.exe -X POST http://localhost:8000/os/inter-api/lpr/recognitions \
  -F "file=@examples/车牌.jpg"
```

配置接口密钥后：

```bash
curl.exe -X POST http://localhost:8000/os/inter-api/lpr/recognitions \
  -H "X-API-Key: replace-with-a-long-random-key" \
  -F "file=@examples/车牌.jpg"
```

支持的上传内容类型必须是图片，默认最大 10 MB，由 `MAX_UPLOAD_BYTES` 控制。

### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "request_id": "3d46c1f6c4be4f64a7b3f2b3f4fd6d5a",
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
    }
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | `0` 表示成功。 |
| `message` | string | 结果说明。 |
| `data.request_id` | string | 请求唯一编号，也会通过 `X-Request-ID` 响应头返回。 |
| `data.plate_number` | string | 标准化后的车牌号。 |
| `data.recognized_at` | datetime | 识别完成时间，UTC，带 `Z`。 |
| `data.processing_time_ms` | number | 服务端实际推理耗时，不包含上传和排队时间。 |
| `data.confidence` | number | 模型置信度，范围 0 到 1。 |
| `data.plate_box` | object/null | 检测到的车牌区域；旧的 HyperLPR3/RapidOCR 全图链路可能为 `null`。坐标以原图左上角为原点。 |

### 失败响应

```json
{
  "code": 400,
  "message": "只支持上传图片文件",
  "data": {
    "error_code": "INVALID_REQUEST",
    "request_id": "..."
  }
}
```

失败响应的顶层 `code` 与 HTTP 状态码一致。客户端应优先判断 HTTP 状态码，再读取 JSON 中的 `message` 和 `data.error_code`。

常见状态码：

| HTTP 状态码 | 含义 |
| ---: | --- |
| `400` | 请求格式错误或文件类型不支持。 |
| `401` | 未提供接口密钥。 |
| `403` | 接口密钥错误。 |
| `413` | 图片超过大小限制。 |
| `422` | 图片有效，但未识别到车牌。 |
| `503` | 模型未就绪或排队超时。 |

## 健康检查

| 探针 | 路径 | 语义 |
| --- | --- | --- |
| 存活 | `/os/inter-api/lpr/livez` | 只检查进程是否能响应，不检查模型。 |
| 就绪 | `/os/inter-api/lpr/readyz` | 模型已预热，可以接收识别请求。 |
| 启动 | `/os/inter-api/lpr/startupz` | 服务启动流程已完成。 |
| 兼容 | `/os/inter-api/lpr/healthz` | 存活探针兼容别名。 |

Swagger 文档：

<http://localhost:8000/os/inter-api/lpr/docs>

## Kubernetes 探针示例

```yaml
livenessProbe:
  httpGet:
    path: /os/inter-api/lpr/livez
    port: 8000
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /os/inter-api/lpr/readyz
    port: 8000
  periodSeconds: 5

startupProbe:
  httpGet:
    path: /os/inter-api/lpr/startupz
    port: 8000
  failureThreshold: 30
  periodSeconds: 5
```
