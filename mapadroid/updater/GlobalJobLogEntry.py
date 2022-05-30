import dataclasses
from typing import Optional, List

from mapadroid.updater.Autocommand import Autocommand
from mapadroid.updater.JobStatus import JobStatus
from mapadroid.updater.SubJob import SubJob


@dataclasses.dataclass
class GlobalJobLogEntry:
    id: str
    origin: str
    job_name: str
    sub_jobs: List[SubJob] = dataclasses.field(default_factory=list)
    last_status: JobStatus = dataclasses.field(default=JobStatus.INIT, metadata={"by_value": True})
    counter: int = 0
    auto_command_settings: Optional[Autocommand] = None
    # Timestamp of the time the job was last processed
    # merged with lastprocess
    processing_date: Optional[int] = None

    # old log entries
    # The raw return value of the command executed
    returning: Optional[str] = None

    sub_job_index: int = 0
