from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class PickWorkerEndpoint(AbstractMadminRootEndpoint):
    """
    "/pick_worker"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('workerpicker.html')
    async def get(self):
        jobname: Optional[str] = self._request.query.get("jobname")
        worker_type: Optional[str] = self._request.query.get("type")
        return {
            "title": "Select worker",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "jobname": jobname,
            "type": worker_type
        }
