from abc import ABC


class AbstractWorkerStats(ABC):
    def __init__(self, worker: str):
        self._worker: str = worker
