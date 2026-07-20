# 第三方组件与模型说明

## yolo26-plate

- 来源：[we0091234/yolo26-plate](https://github.com/we0091234/yolo26-plate)
- 集成上游提交：`72fdaaf8b6b16115fa697f4c7f1bb101a34ae0c5`
- 许可证：AGPL-3.0，许可证全文见项目根目录 [LICENSE](LICENSE)
- 集成内容：YOLO26 Pose 的车牌框、单层/双层类别、四角关键点处理，以及 `plate_rec_color` 字符模型的推理后处理
- 本项目改动：移除在线服务对 PyTorch/Ultralytics 的运行时依赖，使用 ONNX Runtime 加载导出的检测和识别模型；保留透视矫正和双层车牌上下行拼接逻辑

## 模型文件

`models/plate_detector/` 中的以下文件由上游权重导出或转换而来，随本项目按 AGPL-3.0 及上游适用条款分发：

- `yolo26s-plate-detect.onnx`：YOLO26 Pose 检测模型
- `plate_rec_color.onnx`：车牌字符和颜色识别模型

模型具体来源、输入输出和 SHA-256 见 [models/plate_detector/README.md](models/plate_detector/README.md)。

## 其他检测器

当前目录中的 YOLOv9 通用车牌检测模型来自 [ankandrew/open-image-models](https://github.com/ankandrew/open-image-models)，代码仓库标注 MIT；正式商用时仍应独立核对模型权重和训练数据授权。
