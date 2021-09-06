import mock
import pytest

from mapadroid.mad_apk.wizard import APKWizard
from mapadroid.utils.functions import get_version_codes


@pytest.fixture(scope='function')
def wiz_instance(db_wrapper):
    storage = mock.Mock()
    return APKWizard(db_wrapper, storage, "CoolToken")


@pytest.fixture(autouse=True)
def clear_cache():
    yield
    get_version_codes.cache_clear()


@pytest.fixture(autouse=True)
def mock_version_codes():
    with mock.patch("mapadroid.utils.functions.open", new_callable=mock.mock_open, read_data="{}"):
        yield
