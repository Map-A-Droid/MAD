from io import BytesIO
from typing import Optional

from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import SettingsAuth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator
from mapadroid.utils.PDConfig import PDConfig


class AutoconfigDownloadEndpoint(AbstractMadminRootEndpoint):
    """
    "/autoconfig/download"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        ac_issues = AutoConfIssueGenerator()
        await ac_issues.setup(self._session, self._get_instance_id(),
                              self._get_mad_args(), self._get_storage_obj())
        if ac_issues.has_blockers():
            return await self._json_response('Basic requirements not met', status=406, headers=ac_issues.get_headers())
        pd_conf = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
        await pd_conf.load_config()
        config_file = BytesIO()
        info = [pd_conf.contents['post_destination']]
        try:
            if pd_conf.contents['mad_auth'] is not None:
                auth: Optional[SettingsAuth] = await SettingsAuthHelper.get(self._session, self._get_instance_id(),
                                                                            pd_conf.contents['mad_auth'])
                if auth is not None:
                    info.append(f"{auth.username}:{auth.password}")
        except KeyError:
            # No auth defined for RGC so theres probably no auth for the system
            pass
        # TODO: Async executor?
        config_file.write('\n'.join(info).encode('utf-8'))
        config_file.seek(0, 0)
        # TODO: Verify working, otherwise see below
        # return web.FileResponse(config_file, headers={'Content-Disposition': 'Attachment'})
        return web.Response(
            headers={'Content-Disposition': 'Attachment; filename="mad_autoconf.txt"',
                     'Content-Type': 'text/plain'},
            body=config_file
        )
