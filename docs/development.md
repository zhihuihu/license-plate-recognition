# 开发与扩展

## 项目结构

```text
app/
├── main.py                    # FastAPI 应用、路由和生命周期
├── config.py                  # 环境变量配置
├── service.py                 # 识别编排和耗时统计
├── schemas.py                 # 请求和响应模型
├── security.py                # API Key 鉴权
├── middleware.py              # 请求 ID 和访问日志
├── errors.py                  # 统一错误响应
├── web/index.html             # 内置手动识别页面
└── recognizer/
    ├── hyperlpr_engine.py     # HyperLPR3 主引擎
    ├── paddleocr_engine.py    # PaddleOCR 复核引擎
    ├── rapidocr_engine.py     # RapidOCR 兜底引擎
    ├── fallback.py            # 低置信度回退链
    ├── pool.py                # 多实例池
    └── plate_text.py          # 车牌清洗和校验
```

识别链路：

```text
上传图片 → HyperLPR3 → PaddleOCR 复核 → RapidOCR 兜底 → 车牌标准化 → 统一响应
```

当前牌型支持范围和不能承诺的场景见 [plate-types.md](plate-types.md)。

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OCR_ENGINE = "hyperlpr3"
$env:PRELOAD_OCR_MODEL = "true"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

当前 Windows Python 3.14 环境可以使用 HyperLPR3 和 RapidOCR。PaddleOCR 需要匹配的 PaddlePaddle 环境；项目已经准备了 Python 3.13 的离线资源，具体见 [../offline/README.md](../offline/README.md)。生产 Docker 镜像使用 Python 3.13 和固定 PaddleOCR 版本。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app tests
```

测试覆盖：

- 统一响应结构和错误处理
- API Key 鉴权
- 识别回退链路
- 多实例池和排队行为
- PaddleOCR 2.x/3.x 输出解析
- 页面静态路由

## 新增识别引擎

1. 在 `app/recognizer/` 中新增引擎适配器，实现 `warmup()` 和 `recognize(image_bytes)`。
2. 返回 `PlateCandidate(plate_number, confidence)`，不要在适配器中直接改变 API 响应结构。
3. 在 `app/main.py` 的 `_create_recognizer()` 中接入引擎或回退链。
4. 增加没有模型下载、模型加载失败、低置信度和正常识别测试。
5. 重新执行测试、离线资源校验和目标机器压测。

## 后续停车场能力

当前服务是“单张图片识别”服务。生产停车场可以继续扩展：

- 摄像头视频流接入和多帧投票
- 车辆进出事件、车道和相机编号
- 同车牌去重、入场/出场状态机
- 黑名单、白名单和收费系统对接
- Prometheus 指标、日志审计和告警
- 识别图片保留策略、脱敏和访问控制

这些能力建议放在独立的业务编排层，不要把停车场订单和收费状态直接塞入 OCR 引擎适配器。

## 自研模型训练

不要在当前在线服务中加入训练代码。建议单独创建 `license-plate-training` 项目：

```text
license-plate-training/
├── datasets/       # 检测框、四点标注、车牌裁剪图和标签
├── configs/        # 训练参数
├── scripts/        # 数据转换、训练、评估
├── checkpoints/    # 训练过程权重
└── exports/        # 部署模型
```

训练流程：

1. 采集目标停车场真实图片，覆盖白天、夜间、逆光、雨天、反光、斜拍、模糊和双层车牌。
2. 标注车牌位置，训练或微调检测模型。
3. 对车牌裁剪、透视矫正并标注完整车牌号，训练或微调识别模型。
4. 优先基于 PaddleOCR 预训练模型微调，不建议从零训练。
5. 分别评估检测召回率、单字符准确率和整张车牌完全正确率。
6. 用不同车辆、时间和摄像头的独立测试集验证，达标后导出本地模型并通过新的适配器接入。

合成车牌图片只能用于预训练或补充字符样本，不能代替真实停车场数据。训练文档应以 [PaddleOCR 文本检测训练文档](https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/detection.html)和[文本识别训练文档](https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_train/recognition.html)的当前版本为准。

## 商用发布检查

- 为服务配置高强度 `API_KEYS`，不要提交 `.env`。
- 使用真实现场独立数据集验收，不要把置信度当成业务正确率。
- 根据吞吐率、P95 延迟和内存选择 `OCR_INSTANCE_COUNT`。
- 审查 HyperLPR3、PaddleOCR、PaddlePaddle、RapidOCR 和模型的许可证。
- 对上传图片设置访问控制、保留期限、脱敏和审计策略。
