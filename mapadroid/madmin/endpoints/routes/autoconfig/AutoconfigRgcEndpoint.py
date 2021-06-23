from typing import List, Dict

import aiohttp_jinja2
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import SettingsAuth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.RGCConfig import RGCConfig


class AutoconfigRgcEndpoint(AbstractMadminRootEndpoint):
    """
    "/autoconfig/rgc"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    @aiohttp_jinja2.template('autoconfig_config_editor.html')
    async def get(self):
        config = RGCConfig(self._session, self._get_instance_id(), self._get_mad_args())
        await config.load_config()
        auths: Dict[int, SettingsAuth] = await SettingsAuthHelper.get_all_mapped(self._session, self._get_instance_id())
        uri = self._url_for('api_autoconf_rgc')
        return {"subtab": "autoconf_rgc",
                "config_name": 'Remote GPS Controller',
                "config_element": config,
                "auths": auths,
                "uri": uri
                }
