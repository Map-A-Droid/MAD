from typing import List

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import AutoconfigRegistration, SettingsDevice, SettingsPogoauth
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator


class AutoconfigPendingSessionEndpoint(AbstractRootEndpoint):
    """
    "/autoconfig/pending/<int:session_id>"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    @aiohttp_jinja2.template('autoconfig_pending_dev.html')
    async def get(self):
        session_id: int = int(self.request.match_info['session_id'])

        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, instance_id=self._get_instance_id(), session_id=session_id)
        if not sessions:
            raise web.HTTPFound(url_for('autoconfig_pending'))
        ac_issues = AutoConfIssueGenerator()
        await ac_issues.setup(self._session, self._get_instance_id(),
                              self._get_mad_args(), self._get_storage_obj())
        _, issues_critical = ac_issues.get_issues()
        if issues_critical:
            raise web.HTTPFound(url_for('autoconfig_pending'))
        registration_session: AutoconfigRegistration = sessions[0]
        pogoauths: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_of_autoconfig(self._session,
                                                                                           self._get_instance_id(),
                                                                                           registration_session.device_id)
        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(self._session, self._get_instance_id())
        uri = "{}/{}".format(url_for('api_autoconf'), session_id)
        redir_uri = url_for('autoconfig_pending')
        return {"subtab": "autoconf_dev",
                "element": registration_session,
                "devices": devices,
                "accounts": pogoauths,
                "uri": uri,
                "redirect": redir_uri,
                "method": 'POST'
                }
