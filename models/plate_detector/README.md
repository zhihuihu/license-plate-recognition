# YOLOv9 车牌检测模型

当前文件是 `yolo-v9-t-384-license-plates-end2end.onnx`，用于检测图片中的车牌区域，不负责识别文字。

- 来源项目：[open-image-models](https://github.com/ankandrew/open-image-models)
- 模型来源：[GitHub Release](https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-t-384-license-plates-end2end.onnx)
- 模型输入：`1 x 3 x 384 x 384`，CPU 使用 ONNX Runtime 推理
- SHA-256：`888397b96d761c89db40bc9c305838e8652660f5e282c2cadebbe8d2951a77a8`
- 代码仓库许可证：MIT；正式商用前仍应核对具体模型权重和训练数据的授权条款

服务使用这个模型输出的车牌框，再将裁剪后的区域交给本地 PaddleOCR。它是通用车牌检测器，不等同于中国特殊牌型专用检测器；现场数据验收后，可用同一 ONNX 接口替换为自训的中国车牌检测模型。
