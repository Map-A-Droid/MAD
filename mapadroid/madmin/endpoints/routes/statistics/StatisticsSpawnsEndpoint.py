import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import \
    AbstractStatisticsRootEndpoint


class StatisticsSpawnsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/statistics_spawns"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/spawn_statistics.html')
    @expand_context()
    async def get(self):
        return {
            "title": "MAD Spawnpoint Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
