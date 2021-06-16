import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class StatisticsStopQuestEndpoint(AbstractMadminRootEndpoint):
    """
    "/statistics_stop_quest"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/stop_quest_statistics.html')
    async def get(self):
        return {
            "title": "MAD Stop/Quest Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
