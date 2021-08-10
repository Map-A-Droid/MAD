import asyncio
from datetime import datetime
from typing import Optional

from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils.collections import Location
from mapadroid.utils.pogoevent import PogoEvent
from mapadroid.utils.madConstants import TIMESTAMP_NEVER
from mapadroid.utils.madGlobals import TransportType
from mapadroid.utils.resolution import ResolutionCalculator


class WorkerState:
    def __init__(self, origin: str, device_id: int, stop_worker_event: asyncio.Event, active_event: PogoEvent):
        self.device_id: int = device_id
        self.origin: str = origin
        self.stop_worker_event: asyncio.Event = stop_worker_event
        self.resolution_calculator: ResolutionCalculator = ResolutionCalculator()
        self.active_event: PogoEvent = active_event

        self.current_location = Location(0.0, 0.0)
        self.last_location = Location(0.0, 0.0)
        self.location_count: int = 0
        self.login_error_count: int = 0
        self.last_transport_type: TransportType = TransportType.TELEPORT
        self.last_screenshot_taken_at: int = TIMESTAMP_NEVER
        self.last_screen_type: ScreenType = ScreenType.UNDEFINED
        self.current_sleep_duration: int = 0
        self.last_received_data_time: Optional[datetime] = None
        self.restart_count: int = 0
        self.reboot_count: int = 0
        self.same_screen_count: int = 0


