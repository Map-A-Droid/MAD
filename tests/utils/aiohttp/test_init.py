import unittest

from yarl import URL
from mapadroid.utils.aiohttp import add_prefix_to_url


class TestAiohttpInitUtils(unittest.TestCase):
    def test_add_prefix_to_url(self):
        prefix = "/admin/"
        url_used = URL("/status")

        prefixed = add_prefix_to_url(prefix, url_used)
        assert prefixed.path.startswith(prefix)
