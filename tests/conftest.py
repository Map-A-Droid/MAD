import os
from glob import glob

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
