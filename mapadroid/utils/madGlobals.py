from enum import Enum
from multiprocessing import Event

terminate_mad = Event()


class WebsocketWorkerRemovedException(Exception):
    pass


class MitmReceiverRetry(Exception):
    pass


class WebsocketWorkerConnectionClosedException(Exception):
    pass


class WebsocketWorkerTimeoutException(Exception):
    pass


class WrongAreaInWalker(Exception):
    pass


class InternalStopWorkerException(Exception):
    """
    Exception to be called in derived worker methods to signal stops of the worker
    """
    pass


class ScreenshotType(Enum):
    JPEG = 0
    PNG = 1


class TeamColours(Enum):
    YELLOW = "Yellow"
    BLUE = "Blue"
    RED = "Red"
    WHITE = "White"

