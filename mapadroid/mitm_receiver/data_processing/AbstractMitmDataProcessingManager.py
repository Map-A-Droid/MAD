import asyncio
from abc import ABC


class AbstractMitmDataProcessingManager(ABC):
    _mitm_data_queue: asyncio.Queue

    def __init__(self):
        super(AbstractMitmDataProcessingManager, self).__init__()
        self._mitm_data_queue = asyncio.Queue()

    def get_queue(self) -> asyncio.Queue:
        return self._mitm_data_queue
