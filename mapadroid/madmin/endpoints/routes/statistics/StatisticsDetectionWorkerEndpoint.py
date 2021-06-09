from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class StatisticsDetectionWorkerEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/statistics_detection_worker"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics_worker.html')
    async def get(self):
        worker: Optional[str] = self._request.query.get("worker")
        return {
            "title": "MAD Worker Statistics",
            "time": self._get_mad_args().madmin_time,
            "minutes_usage": self._get_minutes_usage_query_args(),
            "worker": worker,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
