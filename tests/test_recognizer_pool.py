from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.recognizer.base import PlateCandidate
from app.recognizer.pool import RecognizerPool


class FakeRecognizer:
    def __init__(self, instance_id: int, used_ids: list[int], used_ids_lock: Lock) -> None:
        self.instance_id = instance_id
        self.used_ids = used_ids
        self.used_ids_lock = used_ids_lock

    def recognize(self, _: bytes) -> PlateCandidate:
        with self.used_ids_lock:
            self.used_ids.append(self.instance_id)
        return PlateCandidate("苏A8K2N6", 0.99)


def test_pool_creates_configured_instances_and_recognizes():
    used_ids: list[int] = []
    used_ids_lock = Lock()
    next_id = 0

    def factory() -> FakeRecognizer:
        nonlocal next_id
        instance_id = next_id
        next_id += 1
        return FakeRecognizer(instance_id, used_ids, used_ids_lock)

    pool = RecognizerPool(factory, size=3)
    pool.warmup()

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(pool.recognize, [b"image"] * 6))

    assert pool.size == 3
    assert len(results) == 6
    assert set(used_ids) == {0, 1, 2}
