import dataclasses
from typing import Union
from marshmallow_enum import EnumField
from mapadroid.updater.GlobalJobLogAlgoType import GlobalJobLogAlgoType


@dataclasses.dataclass
class Autocommand:
    redo: bool
    algo_value: Union[int, str]
    start_with_init: bool
    origins: str
    # The job to be executed referenced by its name
    job: str
    redo_on_error: bool
    algo_type: GlobalJobLogAlgoType = dataclasses.field(default=GlobalJobLogAlgoType.LOOP, metadata={"by_value": True})
