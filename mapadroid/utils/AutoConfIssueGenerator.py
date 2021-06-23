import json
from enum import IntEnum
from typing import List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import SettingsPogoauth, SettingsAuth
from mapadroid.mad_apk.utils import get_apk_status
from mapadroid.utils.PDConfig import PDConfig
from mapadroid.utils.RGCConfig import RGCConfig
from mapadroid.utils.autoconfig import validate_hopper_ready
from aiohttp.abc import Request


class AutoConfIssues(IntEnum):
    no_ggl_login = 1
    origin_hopper_not_ready = 2
    auth_not_configured = 3
    pd_not_configured = 4
    rgc_not_configured = 5
    package_missing = 6


class AutoConfIssueGenerator(object):
    def __init__(self, ):
        self.warnings: List[AutoConfIssues] = []
        self.critical: List[AutoConfIssues] = []

    # TODO: Async-style init rather than sync init with async setup
    async def setup(self, session: AsyncSession, instance_id: int, args, storage_obj):
        pogoauth_entries: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_unassigned(session, instance_id,
                                                                                               None)
        if len(pogoauth_entries) == 0 and not args.autoconfig_no_auth:
            self.warnings.append(AutoConfIssues.no_ggl_login)
        if not await validate_hopper_ready(session, instance_id):
            self.critical.append(AutoConfIssues.origin_hopper_not_ready)
        auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, instance_id)
        if len(auths) == 0:
            self.warnings.append(AutoConfIssues.auth_not_configured)

        pd_config = PDConfig(session, instance_id, args)
        await pd_config.load_config()
        if not pd_config.configured:
            self.critical.append(AutoConfIssues.pd_not_configured)
        rgc_config = RGCConfig(session, instance_id, args)
        await rgc_config.load_config()
        if not rgc_config.configured:
            self.critical.append(AutoConfIssues.rgc_not_configured)
        missing_packages = []
        for _, apkpackages in (await get_apk_status(storage_obj)).items():
            for _, package in apkpackages.items():
                if package.version is None:
                    missing_packages.append(package)
        if missing_packages:
            self.critical.append(AutoConfIssues.package_missing)

    def get_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            'X-Critical': json.dumps([issue.value for issue in self.critical]),
            'X-Warnings': json.dumps([issue.value for issue in self.warnings])
        }
        return headers

    def get_issues(self, request: Request) -> Tuple[List[str], List[str]]:
        issues_warning = []
        issues_critical = []
        # Warning messages
        if AutoConfIssues.no_ggl_login in self.warnings:
            link = request.app.router['settings_pogoauth'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">PogoAuth</a>"
            issues_warning.append("No available Google logins for auto creation of devices. Configure through "
                                  f"{anchor}")
        if AutoConfIssues.auth_not_configured in self.warnings:
            link = request.app.router['settings_auth'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">Auth</a>"
            issues_warning.append(f"No auth configured which is a potential security risk. Configure through {anchor}")
        # Critical messages
        if AutoConfIssues.origin_hopper_not_ready in self.critical:
            link = request.app.router['settings_walkers'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">Walker</a>"
            issues_critical.append(f"No walkers configured. Configure through {anchor}")
        if AutoConfIssues.pd_not_configured in self.critical:
            link = request.app.router['autoconf_pd'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">PogoDroid Configuration</a>"
            issues_critical.append(f"PogoDroid is not configured. Configure through {anchor}")
        if AutoConfIssues.rgc_not_configured in self.critical:
            link = request.app.router['autoconf_rgc'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">RemoteGPSController Configuration</a>"
            issues_critical.append(f"RGC is not configured. Configure through {anchor}")
        if AutoConfIssues.package_missing in self.critical:
            link = request.app.router['mad_apks'].url_for()
            anchor = f"<a class=\"alert-link\" href=\"{link}\">MADmin Packages</a>"
            issues_critical.append(f"Missing one or more required packages. Configure through {anchor}")
        return issues_warning, issues_critical

    def has_blockers(self) -> bool:
        return len(self.critical) > 0
