import time
from typing import List, Optional, Union

from aiohttp_jinja2.helpers import url_for
from multidict._multidict import MultiDictProxy

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
            await self._get_device_updater().preadd_job(device, jobname, int(time.time()), job_type)
            # time.sleep(1)

        await self._add_notice_message('Job successfully queued')
        await self._redirect(self._url_for('install_status'))
