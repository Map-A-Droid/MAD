from typing import List, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import (SettingsArea, SettingsAreaRaidsMitm,
                                SettingsRoutecalc)
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerIV import RouteManagerIV
from mapadroid.route.RouteManagerLeveling import RouteManagerLeveling
from mapadroid.route.RouteManagerLevelingRoutefree import \
    RouteManagerLevelingRoutefree
from mapadroid.route.RouteManagerMon import RouteManagerMon
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.route.RouteManagerRaids import RouteManagerRaids
from mapadroid.utils.collections import Location
from mapadroid.worker.WorkerType import WorkerType


class RouteManagerFactory:
    @staticmethod
    def get_routemanager(db_wrapper: DbWrapper, area: SettingsArea, coords: Optional[List[Location]],
                         max_radius: int, max_coords_within_radius: int,
                         geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc, use_s2: bool = False,
                         s2_level: int = 15, joinqueue=None, include_event_id=None):

        if area.mode == WorkerType.RAID_MITM.value:
            area: SettingsAreaRaidsMitm = area
            route_manager = RouteManagerRaids(db_wrapper=db_wrapper, area=area, coords=coords, max_radius=max_radius,
                                              max_coords_within_radius=max_coords_within_radius,
                                              geofence_helper=geofence_helper, routecalc=routecalc,
                                              joinqueue=joinqueue,
                                              use_s2=use_s2, s2_level=s2_level
                                              )
        elif mode == WorkerType.MON_MITM.value:
            route_manager = RouteManagerMon(db_wrapper, dbm, area_id, coords, max_radius,
                                            max_coords_within_radius,
                                            path_to_include_geofence, path_to_exclude_geofence, routefile,
                                            mode=mode, settings=settings, init=init, name=name,
                                            joinqueue=joinqueue,
                                            coords_spawns_known=coords_spawns_known,
                                            include_event_id=include_event_id
                                            )
        elif mode == WorkerType.IV_MITM.value:
            route_manager = RouteManagerIV(db_wrapper, dbm, area_id, coords, 0, 99999999,
                                           path_to_include_geofence, path_to_exclude_geofence, routefile,
                                           mode=mode, settings=settings, init=False, name=name,
                                           joinqueue=joinqueue
                                           )
        elif mode == WorkerType.IDLE.value:
            route_manager = RouteManagerRaids(db_wrapper, dbm, area_id, coords, max_radius,
                                              max_coords_within_radius,
                                              path_to_include_geofence, path_to_exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name,
                                              joinqueue=joinqueue
                                              )
        elif mode == WorkerType.STOPS.value:
            if level and calctype == 'routefree':
                route_manager = RouteManagerLevelingRoutefree(db_wrapper, dbm, area_id, coords, max_radius,
                                                              max_coords_within_radius,
                                                              path_to_include_geofence, path_to_exclude_geofence,
                                                              routefile,
                                                              mode=mode, settings=settings, init=init, name=name,
                                                              level=True,
                                                              calctype=calctype, joinqueue=joinqueue
                                                              )
            elif level:
                route_manager = RouteManagerLeveling(db_wrapper, dbm, area_id, coords, max_radius,
                                                     max_coords_within_radius,
                                                     path_to_include_geofence, path_to_exclude_geofence,
                                                     routefile,
                                                     mode=mode, settings=settings, init=init, name=name,
                                                     level=True,
                                                     calctype=calctype, joinqueue=joinqueue
                                                     )
            else:
                route_manager = RouteManagerQuests(db_wrapper, dbm, area_id, coords, max_radius,
                                                   max_coords_within_radius,
                                                   path_to_include_geofence, path_to_exclude_geofence,
                                                   routefile,
                                                   mode=mode, settings=settings, init=init, name=name,
                                                   level=level,
                                                   calctype=calctype, joinqueue=joinqueue
                                                   )
        else:
            raise RuntimeError("Invalid mode found in mapping parser.")
        return route_manager
