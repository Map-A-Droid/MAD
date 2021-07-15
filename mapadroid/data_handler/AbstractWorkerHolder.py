from abc import ABC


class AbstractWorkerHolder(ABC):
    def __init__(self, worker: str):
        self._worker: str = worker
