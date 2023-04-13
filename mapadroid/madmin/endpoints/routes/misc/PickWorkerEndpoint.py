from typing import Optional

import aiohttp_jinja2

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)


class PickWorkerEndpoint(AbstractMadminRootEndpoint):
    """
    "/pick_worker"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('workerpicker.html')
    @expand_context()
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
