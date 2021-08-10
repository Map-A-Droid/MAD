import asyncio
from typing import Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.model import TrsEvent
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.utils)


class PogoEvent:
    def __init__(self, args, db_wrapper: DbWrapper):
        self.args = args
        self._db_wrapper = db_wrapper
        self._event_id: int = 1
        self._lure_duration: int = 30

    async def event_checker(self):
        while True:
            async with self._db_wrapper as session, session:
                active_event: Optional[TrsEvent] = await TrsEventHelper.get_current_event(session)
                if active_event:
                    self._event_id = active_event.id
                    self._lure_duration = active_event.event_lure_duration
                else:
                    self._event_id = 1
                    self._lure_duration = 30
                self._db_wrapper.set_event_id(self._event_id)
            await asyncio.sleep(60)

    async def start_event_checker(self):
        if not self.args.no_event_checker:
            loop = asyncio.get_running_loop()
            loop.create_task(self.event_checker())

    def get_current_event_id(self):
        return self._event_id
