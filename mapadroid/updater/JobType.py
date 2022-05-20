from enum import Enum


class JobType(Enum):
    INSTALLATION = "jobType.INSTALLATION"
    REBOOT = "jobType.REBOOT"
    RESTART = "jobType.RESTART"
    STOP = "jobType.STOP"
    PASSTHROUGH = "jobType.PASSTHROUGH"
    START = "jobType.START"
    SMART_UPDATE = "jobType.SMART_UPDATE"
    CHAIN = "jobType.CHAIN"
