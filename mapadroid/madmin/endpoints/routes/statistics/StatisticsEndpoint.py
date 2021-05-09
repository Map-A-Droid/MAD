from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.RootEndpoint import RootEndpoint


class StatisticsEndpoint(RootEndpoint):
    """
    "/statistics"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/statistics.html')
    async def get(self):
        minutes_usage: Optional[int] = self._request.query.get("minutes_usage")
        if not minutes_usage:
            minutes_usage = 120
        return {
            "title": "MAD Statistics",
            "time": self._get_mad_args().madmin_time,
            "minutes_usage": minutes_usage,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
