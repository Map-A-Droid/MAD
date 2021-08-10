from enum import Enum


class ReceivedType(Enum):
    UNDEFINED = -1
    GYM = 0
    STOP = 2
    MON = 3
    CLEAR = 4
    GMO = 5
    FORT_SEARCH_RESULT = 6
