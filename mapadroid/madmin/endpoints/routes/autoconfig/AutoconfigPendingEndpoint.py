from typing import List, Tuple

import aiohttp_jinja2
from aiohttp.abc import Request

from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.model import (AuthLevel, AutoconfigRegistration,
                                SettingsDevice)
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator


class AutoconfigPendingEndpoint(AbstractMadminRootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('autoconfig_pending.html')
    @expand_context()
    async def get(self):
        ac_issues = AutoConfIssueGenerator()
        await ac_issues.setup(self._session, self._get_instance_id(),
                              self._get_mad_args(), self._get_storage_obj())
        issues_warning, issues_critical = ac_issues.get_issues(self.request)
        pending_entries: List[Tuple[AutoconfigRegistration, SettingsDevice]] = \
            await AutoconfigRegistrationHelper.get_pending(self._session, self._get_instance_id())

        return {"subtab": "autoconf_dev",
                "pending": pending_entries,
                "issues_warning": issues_warning,
                "issues_critical": issues_critical
                }
