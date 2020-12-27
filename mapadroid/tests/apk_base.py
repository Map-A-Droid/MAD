from unittest import TestCase

from mapadroid.tests.test_utils import get_connection_api, get_connection_mitm


class APKTestBase(TestCase):
    def setUp(self):
        self.api = get_connection_api()
        self.mitm = get_connection_mitm(self.api)

    def tearDown(self):
        self.api.close()
        self.mitm.close()
