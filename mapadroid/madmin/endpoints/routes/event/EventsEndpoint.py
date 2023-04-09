import aiohttp_jinja2

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)


class EventsEndpoint(AbstractMadminRootEndpoint):
    """
    "/statistics"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('events.html')
    @expand_context()
    async def get(self):
        return {
            "title": "MAD Events",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower()
        }
