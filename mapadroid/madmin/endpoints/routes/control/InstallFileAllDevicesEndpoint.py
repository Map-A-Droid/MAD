import asyncio
import math
import time
from typing import Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class InstallFileAllDevicesEndpoint(AbstractControlEndpoint):
    """
    "/install_file_all_devices"
    """

    # TODO: Auth
    # TODO: Also "post"?
    async def get(self):
        jobname: Optional[str] = self.request.query.get('jobname')
        job_type_raw: Optional[str] = self.request.query.get('type')
        if not jobname or not job_type_raw:
            await self._add_notice_message("No File or Type selected")
            await self._redirect(self._url_for('install_status'))

        devices = await self._get_mapping_manager().get_all_devicenames()
        for device in devices:
            await self._get_device_updater().add_job(device, jobname)

        await self._add_notice_message('Job successfully queued')
        await self._redirect(self._url_for('install_status'))
