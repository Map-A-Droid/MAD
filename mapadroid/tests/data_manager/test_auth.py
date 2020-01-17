from mapadroid.tests.data_manager.base import DataManagerBase
from mapadroid.utils.data_manager.modules.auth import Auth


class DMAuth(DataManagerBase):
    base_resource = Auth

    def test_echo(self):
        self.assertTrue(False)
