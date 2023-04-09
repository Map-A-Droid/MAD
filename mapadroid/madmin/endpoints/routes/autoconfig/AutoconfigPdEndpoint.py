from typing import Dict

import aiohttp_jinja2
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import AuthLevel, SettingsAuth
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)
from mapadroid.utils.PDConfig import PDConfig


class AutoconfigPdEndpoint(AbstractMadminRootEndpoint):
    """
    "/autoconfig/pd"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('autoconfig_config_editor.html')
    @expand_context()
    async def get(self):
        config = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
        await config.load_config()
        auths: Dict[int, SettingsAuth] = await SettingsAuthHelper.get_all_mapped(self._session, self._get_instance_id())
        uri = self._url_for('api_autoconf_pd')
        return {"subtab": "autoconf_pd",
                "config_name": 'PogoDroid',
                "config_element": config,
                "auths": auths,
                "uri": uri
                }
