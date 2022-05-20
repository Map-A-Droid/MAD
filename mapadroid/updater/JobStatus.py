from enum import Enum


class JobStatus(Enum):
    NONE = "none"
    INIT = "init"
    PENDING = "pending"
    STARTING = "starting"
    PROCESSING = "processing"
    NOT_CONNECTED = "not connected"
    NOT_REQUIRED = "not required"
    NOT_SUPPORTED = "not supported"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    FAILING = "failing"
    FAILED = "failed"
    FUTURE = "future"
    SUCCESS = "success"
