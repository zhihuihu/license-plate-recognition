# YOLOv9 车牌检测模型

当前文件是 `yolo-v9-t-384-license-plates-end2end.onnx`，用于检测图片中的车牌区域，不负责识别文字。

- 来源项目：[open-image-models](https://github.com/ankandrew/open-image-models)
- 模型来源：[GitHub Release](https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-t-384-license-plates-end2end.onnx)
- 模型输入：`1 x 3 x 384 x 384`，CPU 使用 ONNX Runtime 推理
- SHA-256：`888397b96d761c89db40bc9c305838e8652660f5e282c2cadebbe8d2951a77a8`
- 代码仓库许可证：MIT；正式商用前仍应核对具体模型权重和训练数据的授权条款

服务使用这个模型输出的车牌框，再将裁剪后的区域交给本地 PaddleOCR。它是通用车牌检测器，不等同于中国特殊牌型专用检测器；现场数据验收后，可用同一 ONNX 接口替换为自训的中国车牌检测模型。

## YOLO26 中国车牌专用模型

项目还内置 `yolo26s-plate-detect.onnx` 和 `plate_rec_color.onnx`，由 [we0091234/yolo26-plate](https://github.com/we0091234/yolo26-plate) 的 `yolo26s-plate-detect.pt`、`plate_rec_color.pth` 转换而来。上游使用 YOLO26 Pose 检测车牌框、四角关键点及单层/双层类别；服务随后透视矫正，双层车牌执行上下行拼接，再用专用字符模型识别。

- `yolo26s-plate-detect.onnx`：固定输入 `1 x 3 x 640 x 640`，输出 `1 x 300 x 14`
- `plate_rec_color.onnx`：输入 `1 x 3 x 48 x 168`，输出字符 logits 和颜色 logits
- `yolo26s-plate-detect.onnx` SHA-256：`75C106703D88C048ECA3654D93C768F46436978A4AF8125D0BEF5E6E48E3FED2`
- `plate_rec_color.onnx` SHA-256：`4FAF72754DE5347B0B0028E7341B17D72BC7592E2084EF5D20EADB0D064CFF30`
- 上游许可证：AGPL-3.0，详见项目根目录 [LICENSE](../../LICENSE) 和 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)
