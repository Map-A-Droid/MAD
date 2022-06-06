import dataclasses
from typing import Optional

from mapadroid.updater.JobType import JobType


@dataclasses.dataclass
class SubJob:
    TYPE: JobType = dataclasses.field(default=JobType.CHAIN, metadata={"by_value": True})
    SYNTAX: str = dataclasses.field(default="")
    FIELDNAME: Optional[str] = dataclasses.field(default=None)
    WAITTIME: Optional[int] = dataclasses.field(default=None)

    def __str__(self):
        return str(self.TYPE) + " " + self.SYNTAX[:20] + "..." if len(self.SYNTAX) > 20 else ""
