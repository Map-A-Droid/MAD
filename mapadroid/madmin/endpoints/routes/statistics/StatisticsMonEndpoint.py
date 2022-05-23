import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class StatisticsMonEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/statistics_mon"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/mon_statistics.html')
    @expand_context()
    async def get(self):
        return {
            "title": "MAD Mon Statistics",
            "time": self._get_mad_args().madmin_time,
            "minutes_usage": self._get_minutes_usage_query_args(),
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
