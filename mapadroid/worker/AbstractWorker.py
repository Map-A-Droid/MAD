from abc import ABC, abstractmethod

from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator

from mapadroid.worker.strategy.AbstractWorkerStrategy import AbstractWorkerStrategy


class AbstractWorker(ABC):
    def __init__(self, communicator: AbstractCommunicator, scan_strategy: AbstractWorkerStrategy):
        self._communicator: AbstractCommunicator = communicator
        self._scan_strategy: AbstractWorkerStrategy = scan_strategy

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

    async def set_scan_strategy(self, strategy: AbstractWorkerStrategy) -> None:
        await self._scan_strategy.worker_specific_setup_stop()
        self._scan_strategy = strategy
        await self._scan_strategy_changed()

    @abstractmethod
    async def _scan_strategy_changed(self):
        """
        Routine to be run upon a strategy change
        Returns:

        """
        pass
