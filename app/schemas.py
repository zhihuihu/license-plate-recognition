from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


PayloadT = TypeVar("PayloadT")


class ApiResponse(BaseModel, Generic[PayloadT]):
    """所有业务接口统一使用的响应信封。"""

    code: int = Field(description="业务状态码，0 表示成功，非 0 表示失败")
    message: str = Field(description="结果说明")
    data: PayloadT | None = Field(description="业务数据，失败时通常为错误详情")


class PlateBoxResponse(BaseModel):
    x1: int = Field(ge=0, description="车牌区域左上角 X")
    y1: int = Field(ge=0, description="车牌区域左上角 Y")
    x2: int = Field(ge=0, description="车牌区域右下角 X")
    y2: int = Field(ge=0, description="车牌区域右下角 Y")
    confidence: float = Field(ge=0, le=1, description="检测置信度")


class RecognitionResponse(BaseModel):
    request_id: str = Field(description="用于追踪本次请求的 ID")
    plate_number: str = Field(description="标准化后的车牌号，例如：苏A8K2N6")
    recognized_at: datetime = Field(description="识别完成时间，带时区")
    processing_time_ms: float = Field(ge=0, description="服务端处理耗时，单位毫秒")
    confidence: float = Field(ge=0, le=1, description="OCR 置信度")
    plate_box: PlateBoxResponse | None = Field(default=None, description="检测到的车牌区域")


class ErrorData(BaseModel):
    error_code: str = Field(description="错误类型编码")
    request_id: str = Field(description="用于追踪本次请求的 ID")


class ErrorResponse(ApiResponse[ErrorData]):
    pass
