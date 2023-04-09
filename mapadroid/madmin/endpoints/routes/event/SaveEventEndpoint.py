from datetime import datetime
from typing import Optional, Union

from aiohttp.web_request import FileField
from multidict._multidict import MultiDictProxy

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import \
    check_authorization_header
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class SaveEventEndpoint(AbstractControlEndpoint):
    """
    "/save_event"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def post(self):
        # TODO: Verify str or int?
        form_data: MultiDictProxy[Union[str, bytes, FileField]] = await self.request.post()
        event_id: Optional[str] = form_data.get("id")
        event_name: Optional[str] = form_data.get("event_name")
        # TODO: Verify str
        event_start_date: Optional[str] = form_data.get("event_start_date")
        event_start_time: Optional[str] = form_data.get("event_start_time")
        event_end_date: Optional[str] = form_data.get("event_end_date")
        event_end_time: Optional[str] = form_data.get("event_end_time")
        # TODO: Verify int
        event_lure_duration: Optional[int] = form_data.get("event_lure_duration")

        # default lure duration = 30 (min)
        if event_lure_duration == "":
            event_lure_duration = 30
        if event_name == "" or event_start_date == "" or event_start_time == "" or event_end_date == "" \
                or event_end_time == "":
            await self._add_notice_message('Error while adding this event')
            await self._redirect(self._url_for('events'))

        # TODO: Ensure working conversion
        # TODO: Use self._datetimeformat ?
        event_start = datetime.strptime(event_start_date + " " + event_start_time, '%Y-%m-%d %H:%M')
        event_end = datetime.strptime(event_end_date + " " + event_end_time, '%Y-%m-%d %H:%M')

        await TrsEventHelper.save(self._session, event_name, event_start=event_start,
                                  event_end=event_end,
                                  event_lure_duration=event_lure_duration, event_id=event_id)
        await self._add_notice_message('Successfully added this event')
        await self._redirect(self._url_for('events'), commit=True)
