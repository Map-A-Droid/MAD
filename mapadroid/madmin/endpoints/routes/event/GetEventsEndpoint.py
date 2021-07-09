from typing import List

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.model import TrsEvent
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class GetEventsEndpoint(AbstractControlEndpoint):
    """
    "/get_events"
    """

    # TODO: Auth
    async def get(self):
        all_events: List[TrsEvent] = await TrsEventHelper.get_all(self._session)
        return await self._json_response(all_events)
