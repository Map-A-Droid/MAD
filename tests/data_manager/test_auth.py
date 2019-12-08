import base
from utils import data_manager

class DMAuth(base.DataManagerBase):
    base_resource = data_manager.modules.auth.Auth

    def test_echo(self):
        self.assertTrue(False)