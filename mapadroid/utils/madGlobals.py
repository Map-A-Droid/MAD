from enum import Enum, IntEnum
from threading import Event

from mapadroid.utils.walkerArgs import parse_args

terminate_mad = Event()
application_args = parse_args()


class WebsocketAbortRegistrationException(Exception):
    pass


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


class PrioQueueNoDueEntry(Exception):
    """
    Exception to be called when the prio q is empty during checks
    """
    pass


class NoMaddevApiTokenError(Exception):
    """
    Exception to be called when there is no maddev_api_token set
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


class MonSeenTypes(IntEnum):
    wild = 0
    encounter = 1
    lure_encounter = 2
    lure_wild = 3
    nearby_stop = 4
    nearby_cell = 5


class PositionType(IntEnum):
    NORMAL = 0
    PRIOQ = 1
    STARTUP = 2
    REBOOT = 3
    RESTART = 4


class TransportType(IntEnum):
    TELEPORT = 0
    WALK = 1


class FortSearchResultTypes(Enum):
    UNDEFINED = 0
    QUEST = 1
    TIME = 2
    COOLDOWN = 3
    INVENTORY = 4
    LIMIT = 5
    UNAVAILABLE = 6
    OUT_OF_RANGE = 7
    FULL = 8


class QuestLayer(Enum):
    AR = 0
    NON_AR = 1
