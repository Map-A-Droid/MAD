from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.RootEndpoint import RootEndpoint


class ShinyStatsEndpoint(RootEndpoint):
    """
    "/shiny_stats"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/shiny_statistics.html')
    async def get(self):
        return {
            "title": "MAD Shiny Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
