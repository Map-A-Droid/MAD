from enum import Enum


class JobReturn(Enum):
    UNKNOWN = 0
    SUCCESS = 1
    NOCONNECT = 2
    FAILURE = 3
    TERMINATED = 4
    NOT_REQUIRED = 5
    NOT_SUPPORTED = 6
