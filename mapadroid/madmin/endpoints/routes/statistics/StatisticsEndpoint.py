import aiohttp_jinja2

from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class StatisticsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/statistics"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/statistics.html')
    async def get(self):
        minutes_usage = self._get_minutes_usage_query_args()
        return {
            "title": "MAD Statistics",
            "time": self._get_mad_args().madmin_time,
            "minutes_usage": minutes_usage,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
