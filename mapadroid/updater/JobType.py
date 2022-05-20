from enum import Enum


class JobType(Enum):
    INSTALLATION = 0
    REBOOT = 1
    RESTART = 2
    STOP = 3
    PASSTHROUGH = 4
    START = 5
    SMART_UPDATE = 6
    CHAIN = 99
