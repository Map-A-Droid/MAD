import dataclasses
from typing import Optional, List

from marshmallow_enum import EnumField

from mapadroid.updater.Autocommand import Autocommand
from mapadroid.updater.JobStatus import JobStatus
from mapadroid.updater.SubJob import SubJob


@dataclasses.dataclass(eq=True)
class GlobalJobLogEntry:
    id: str
    origin: str
    job_name: str
    sub_jobs: List[SubJob]
    status: EnumField(JobStatus) = JobStatus.PENDING
    last_status: EnumField(JobStatus) = JobStatus.INIT
    counter: int = 0
    auto_command_settings: Optional[Autocommand] = None
    # Timestamp of the time the job was last processed
    # merged with lastprocess
    processing_date: Optional[int] = None

    last_job_id: Optional[str] = None
    # old log entries
    # The raw return value of the command executed
    returning: Optional[str] = None

    sub_job_index: int = 0
