import pytest

from mapadroid.data_manager import DataManager
from mapadroid.patcher import install_schema, reload_instance_id


@pytest.fixture(scope='session')
@pytest.mark.usefixtures("db_wrapper_real")
def data_manager_real(db_wrapper):
    dm = DataManager(db_wrapper, None)
    install_schema(db_wrapper)
    reload_instance_id(dm)
    yield dm


@pytest.fixture(scope='function')
@pytest.mark.usefixtures("db_wrapper")
def data_manager(db_wrapper):
    db_wrapper.identifier = 1
    dm = DataManager(db_wrapper, db_wrapper.identifier)
    return dm
