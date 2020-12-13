import pytest

from mapadroid.data_manager import DataManager
from mapadroid.patcher import install_schema, reload_instance_id


@pytest.fixture(scope='session')
@pytest.mark.usefixtures("db_wrapper")
def data_manager(db_wrapper):
    dm = DataManager(db_wrapper, None)
    install_schema(db_wrapper)
    reload_instance_id(dm)
    yield dm
