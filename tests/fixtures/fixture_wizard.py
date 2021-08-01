import mock
import pytest

from mapadroid.mad_apk.wizard import APKWizard
from mapadroid.utils.functions import get_version_codes


@pytest.fixture(scope='function')
def wiz_instance(db_wrapper):
    storage = mock.Mock()
    return APKWizard(db_wrapper, storage)


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    get_version_codes.cache_clear()
