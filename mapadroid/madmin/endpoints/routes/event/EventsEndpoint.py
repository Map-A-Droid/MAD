import aiohttp_jinja2

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class EventsEndpoint(AbstractControlEndpoint):
    """
    "/events"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('events.html')
    async def get(self):
        return {
            "title": "MAD Events",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
