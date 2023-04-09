from datetime import datetime
from typing import Optional

import aiohttp_jinja2

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.model import AuthLevel, TrsEvent
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    check_authorization_header, expand_context)
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class EditEventEndpoint(AbstractControlEndpoint):
    """
    "/edit_event"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('event_edit.html')
    @expand_context()
    async def get(self):
        # TODO: Async exec?
        event_id: Optional[str] = self._request.query.get("id")
        event_name: str = ""
        event_start_date: str = ""
        event_start_time: str = ""
        event_end_date: str = ""
        event_end_time: str = ""
        event_lure_duration: int = -1
        event: Optional[TrsEvent] = None
        if event_id:
            event: Optional[TrsEvent] = await TrsEventHelper.get(self._session, int(event_id))
            event_name = event.event_name
            event_lure_duration = event.event_lure_duration
            event_start_date = datetime.strftime(event.event_start, '%Y-%m-%d')
            event_start_time = datetime.strftime(event.event_start, '%H:%M')
            event_end_date = datetime.strftime(event.event_end, '%Y-%m-%d')
            event_end_time = datetime.strftime(event.event_end, '%H:%M')

        return {
            "title": "MAD Add/Edit Event",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "event_name": event_name,
            "event_start_date": event_start_date,
            "event_start_time": event_start_time,
            "event_end_date": event_end_date,
            "event_end_time": event_end_time,
            "event_lure_duration": event_lure_duration,
            "id": event_id
        }
