import dataclasses
from typing import Optional

from marshmallow_enum import EnumField

from mapadroid.updater import JobType


@dataclasses.dataclass
class SubJob:
    TYPE: EnumField(JobType)
    SYNTAX: str
    FIELDNAME: Optional[str]
    WAITTIME: Optional[int]

    def __str__(self):
        return str(self.TYPE) + " " + self.SYNTAX[:20] + "..." if len(self.SYNTAX) > 20 else ""
