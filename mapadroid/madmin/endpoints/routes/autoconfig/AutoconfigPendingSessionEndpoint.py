from typing import List

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import AutoconfigRegistration, SettingsDevice, SettingsPogoauth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint, expand_context
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator


class AutoconfigPendingSessionEndpoint(AbstractMadminRootEndpoint):
    """
    "/autoconfig/pending/<int:session_id>"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    @aiohttp_jinja2.template('autoconfig_pending_dev.html')
    @expand_context()
    async def get(self):
        session_id: int = int(self.request.match_info['session_id'])

        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, instance_id=self._get_instance_id(), session_id=session_id)
        if not sessions:
            raise web.HTTPFound(self._url_for('autoconfig_pending'))
        ac_issues = AutoConfIssueGenerator()
        await ac_issues.setup(self._session, self._get_instance_id(),
                              self._get_mad_args(), self._get_storage_obj())
        _, issues_critical = ac_issues.get_issues(self.request)
        if issues_critical:
            raise web.HTTPFound(self._url_for('autoconfig_pending'))
        registration_session: AutoconfigRegistration = sessions[0]
        pogoauths: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_of_autoconfig(self._session,
                                                                                           self._get_instance_id(),
                                                                                           registration_session.device_id)
        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(self._session, self._get_instance_id())
        uri = "{}/{}".format(self._url_for('api_autoconf'), session_id)
        redir_uri = self._url_for('autoconfig_pending')
        return {"subtab": "autoconf_dev",
                "element": registration_session,
                "devices": devices,
                "accounts": pogoauths,
                "uri": uri,
                "redirect": redir_uri,
                "method": 'POST'
                }
