from __future__ import annotations

import queue
from collections.abc import Callable

from .base import PlateCandidate, PlateRecognizer


class RecognizerPool:
    """管理多个独立 OCR 实例，避免多个请求争抢同一个推理对象。"""

    def __init__(self, factory: Callable[[], PlateRecognizer], size: int) -> None:
        if size <= 0:
            raise ValueError("recognizer pool size must be greater than zero")

        self._instances = [factory() for _ in range(size)]
        self._available: queue.Queue[PlateRecognizer] = queue.Queue(maxsize=size)
        for instance in self._instances:
            self._available.put_nowait(instance)

    @property
    def size(self) -> int:
        return len(self._instances)

    def warmup(self) -> None:
        for instance in self._instances:
            warmup = getattr(instance, "warmup", None)
            if callable(warmup):
                warmup()

    def recognize(self, image_bytes: bytes) -> PlateCandidate:
        # 该方法运行在线程池中，queue.Queue 会让请求等待空闲实例，
        # 同时保证同一个实例不会被多个线程同时调用。
        instance = self._available.get()
        try:
            return instance.recognize(image_bytes)
        finally:
            self._available.put_nowait(instance)
