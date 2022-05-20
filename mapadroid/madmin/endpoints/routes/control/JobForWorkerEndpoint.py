import asyncio
import math
import time
from typing import List, Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class JobForWorkerEndpoint(AbstractControlEndpoint):
    """
    "/job_for_worker"
    """

    # TODO: Auth
    async def get(self):

        jobname: Optional[str] = self.request.query.get('jobname')
        job_type: Optional[str] = self.request.query.get('type')
        devices: Optional[List[str]] = self.request.query.getall('device[]')
        if not devices:
            await self._add_notice_message('No devices specified')
            await self._redirect(self._url_for('install_status'))

        for device in devices:
            job_id: int = int(math.ceil(time.time()))
            await self._get_device_updater().add_job(device, jobname, job_id, job_type)
            await asyncio.sleep(1)

        await self._add_notice_message('Job successfully queued')
        await self._redirect(self._url_for('install_status'))
