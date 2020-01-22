from abc import ABC, abstractmethod


class AbstractWorker(ABC):
    @abstractmethod
    def start_worker(self):
        pass

    @abstractmethod
    def stop_worker(self):
        pass