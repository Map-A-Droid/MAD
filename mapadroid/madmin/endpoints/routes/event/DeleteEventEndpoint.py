from typing import Optional

from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class DeleteEventEndpoint(AbstractControlEndpoint):
    """
    "/del_event"
    """

    # TODO: Auth
    # TODO: rather use "delete"?
    async def post(self):
        # TODO: Verify str or int?
        event_id: Optional[str] = self._request.query.get("id")
        if event_id and await TrsEventHelper.delete_including_spawns(self._session, int(event_id)):
            await self._add_notice_message('Successfully deleted this event')
        else:
            await self._add_notice_message('Could not delete this event')
        await self._redirect(self._url_for('events'), commit=True)
