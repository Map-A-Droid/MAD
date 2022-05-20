import dataclasses
from typing import Union

from mapadroid.updater.GlobalJobLogAlgoType import GlobalJobLogAlgoType


@dataclasses.dataclass
class Autocommand:
    redo: bool
    algo_value: Union[str, int]
    algo_type: GlobalJobLogAlgoType
    start_with_init: bool
    origins: str
    # The job to be executed referenced by its name
    job: str
    redo_on_error: bool

