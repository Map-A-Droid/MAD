from abc import ABC, abstractmethod

from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator


class AbstractWorker(ABC):
    def __init__(self, origin: str, communicator: AbstractCommunicator):
        self._origin: str = origin
        self._communicator: AbstractCommunicator = communicator

    @abstractmethod
    async def start_worker(self):
        pass

    @abstractmethod
    async def stop_worker(self):
        pass

    @abstractmethod
    def is_stopping(self) -> bool:
        pass

    @abstractmethod
    def set_geofix_sleeptime(self, sleeptime: int) -> bool:
        pass

    @property
    def communicator(self) -> AbstractCommunicator:
        return self._communicator

    @communicator.setter
    def communicator(self, value: AbstractCommunicator) -> None:
        raise RuntimeError("Replacing communicator is not supported")

    @property
    def origin(self) -> str:
        return self._origin

    @origin.setter
    def origin(self, value: str) -> None:
        raise RuntimeError("Replacing origin is not supported")
