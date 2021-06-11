import aiohttp_jinja2

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class StatisticsShinyEndpoint(AbstractRootEndpoint):
    """
    "/statistics_shiny"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/shiny_statistics.html')
    async def get(self):
        return {
            "title": "MAD Shiny Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
