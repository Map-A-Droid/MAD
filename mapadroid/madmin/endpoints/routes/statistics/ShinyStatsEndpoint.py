import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import \
    AbstractStatisticsRootEndpoint


class ShinyStatsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/shiny_stats"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/shiny_statistics.html')
    @expand_context()
    async def get(self):
        return {
            "title": "MAD Shiny Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
