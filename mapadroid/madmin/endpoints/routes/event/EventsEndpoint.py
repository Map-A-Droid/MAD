import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint, expand_context


class EventsEndpoint(AbstractMadminRootEndpoint):
    """
    "/statistics"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('events.html')
    @expand_context()
    async def get(self):
        return {
            "title": "MAD Events",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
