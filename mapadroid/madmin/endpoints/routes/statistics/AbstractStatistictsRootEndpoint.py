import datetime
import time
from abc import ABC
from typing import Optional, Dict, Tuple, List

from aiohttp.abc import Request

from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsEvent, TrsSpawn
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import get_geofences, generate_coords_from_geofence


class AbstractStatisticsRootEndpoint(AbstractMadminRootEndpoint, ABC):
    """
    Used for statistics-related endpoints
    """

    def __init__(self, request: Request):
        super().__init__(request)
        self.outdatedays: int = self._get_mad_args().outdated_spawnpoints

    def _generate_mon_icon_url(self, mon_id, form=None, costume=None, shiny=False):
        base_path = 'https://raw.githubusercontent.com/whitewillem/PogoAssets/resized/no_border'

        form_str = '_00'
        if form is not None and str(form) != '0':
            form_str = '_' + str(form)

        costume_str = ''
        if costume is not None and str(costume) != '0':
            costume_str = '_' + str(costume)

        shiny_str = ''
        if shiny:
            shiny_str = '_shiny'

        return "{}/pokemon_icon_{:03d}{}{}{}.png".format(base_path, mon_id, form_str, costume_str, shiny_str)

    def _get_minutes_usage_query_args(self) -> int:
        try:
            minutes_usage: Optional[int] = int(self._request.query.get("minutes_usage"))
        except (ValueError, TypeError):
            minutes_usage = 120
        return minutes_usage

    async def _get_spawn_details_helper(self, area_id: int, event_id: int, today_only: bool = False,
                                        older_than_x_days: Optional[int] = None, sum_only: bool = False, index=0):
        active_spawns: list = []
        possible_fences = await get_geofences(self._get_mapping_manager(), self._session, self._get_instance_id(),
                                              area_id_req=area_id)
        fence: str = await generate_coords_from_geofence(self._get_mapping_manager(), self._session,
                                                         self._get_instance_id(),
                                                         str(list(possible_fences[int(area_id)]['include'].keys())[
                                                                 int(index)]))
        spawns_and_events: Dict[int, Tuple[TrsSpawn, TrsEvent]] = await TrsSpawnHelper \
            .download_spawns(self._session, fence=fence, event_id=event_id, today_only=today_only,
                             older_than_x_days=older_than_x_days)
        if sum_only:
            return len(spawns_and_events)
        for spawn_id, spawn_event in spawns_and_events.items():
            spawn, event = spawn_event
            active_spawns.append({'id': spawn_id, 'lat': spawn.latitude, 'lon': spawn.longitude,
                                  'lastscan': spawn.last_scanned.timestamp(),
                                  'lastnonscan': spawn.last_non_scanned.timestamp()})

        return active_spawns

    async def _get_spawnpoints_of_event(self, spawn_id: int, event_id: int, today_only: bool = False,
                                        older_than_x_days: Optional[int] = None, index=0) -> List[TrsSpawn]:
        possible_fences = await get_geofences(self._get_mapping_manager(), self._session, self._get_instance_id(),
                                              area_id_req=spawn_id)
        fence = await generate_coords_from_geofence(self._get_mapping_manager(), self._session, self._get_instance_id(),
                                                    str(list(possible_fences[int(spawn_id)]['include'].keys())[
                                                            int(index)]))

        spawns_and_events: Dict[int, Tuple[TrsSpawn, TrsEvent]] = await TrsSpawnHelper \
            .download_spawns(self._session, fence=fence, event_id=event_id, today_only=today_only,
                             older_than_x_days=older_than_x_days)
        return [spawn_event[0] for spawn_id, spawn_event in spawns_and_events]
