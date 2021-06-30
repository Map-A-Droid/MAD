from typing import Optional

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class DeleteEventEndpoint(AbstractControlEndpoint):
    """
    "/del_event"
    """

    # TODO: Auth
    # TODO: rather use "delete"?
    async def get(self):
        event_id: Optional[str] = self._request.query.get("id")
        if event_id and await TrsEventHelper.delete_including_spawns(self._session, int(event_id)):
            await self._add_notice_message('Successfully deleted this event')
        else:
            await self._add_notice_message('Could not delete this event')
        await self._redirect(self._url_for('events'), commit=True)
