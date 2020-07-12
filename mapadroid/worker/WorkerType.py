from enum import Enum


class WorkerType(Enum):
    UNDEFINED = None
    RAID_MITM = "raids_mitm"
    MON_MITM = "mon_mitm"
    IV_MITM = "iv_mitm"
    STOPS = "pokestops"
    IDLE = "idle"
    CONFIGMODE = "configmode"
