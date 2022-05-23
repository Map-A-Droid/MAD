from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class MapEndpoint(AbstractControlEndpoint):
    """
    "/map"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('map.html')
    @expand_context()
    async def get(self):
        set_lat: Optional[float] = self._request.query.get("lat")
        set_lng: Optional[float] = self._request.query.get("lng")

        return {
            "lat": self._get_mad_args().home_lat,
            "lng": self._get_mad_args().home_lng,
            "setlat": set_lat,
            "setlng": set_lng,
        }
