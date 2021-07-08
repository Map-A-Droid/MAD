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


class MonSeenTypes(Enum):
    WILD = "wild"
    ENCOUNTER = "encounter"
    LURE_ENCOUNTER = "lure_encounter"
    LURE_WILD = "lure_wild"
    NEARBY_STOP = "nearby_stop"
    NEARBY_CELL = "nearby_cell"
