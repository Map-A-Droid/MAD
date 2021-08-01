import logging
import os
from glob import glob

import pytest
from _pytest.logging import caplog as _caplog  # noqa: F401
from loguru import logger

from mapadroid.utils.logging import init_logging
from mapadroid.utils.walkerArgs import parse_args

os.environ["MODE"] = "DEV"
args = parse_args()
os.environ['LANGUAGE'] = args.language
init_logging(args)


def refactor(string: str) -> str:
    return string.replace("/", ".").replace("\\", ".").replace(".py", "")


pytest_plugins = [
    refactor(fixture) for fixture in glob("tests/fixtures/*.py") if "__" not in fixture
]


@pytest.fixture
def caplog(_caplog): # noqa: F811 E261
    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropogateHandler(), format="{message}")
    yield _caplog
    logger.remove(handler_id)
