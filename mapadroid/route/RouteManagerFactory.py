from typing import Optional

from mapadroid.data_manager.modules import GeoFence, RouteCalc
from mapadroid.route.RouteManagerMon import RouteManagerMon
from mapadroid.route.RouteManagerIV import RouteManagerIV
from mapadroid.route.RouteManagerLeveling import RouteManagerLeveling
from mapadroid.route.RouteManagerLevelingRoutefree import RouteManagerLevelingRoutefree
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.route.RouteManagerRaids import RouteManagerRaids
from mapadroid.worker.WorkerType import WorkerType


class RouteManagerFactory:
    @staticmethod
    def get_routemanager(db_wrapper, dbm, area_id, max_radius, max_coords_within_radius,
                         include_geofence: Optional[GeoFence],
                         exclude_geofence: Optional[GeoFence], routefile: RouteCalc,
                         mode: WorkerType = WorkerType.UNDEFINED, init: bool = False, name: str = "unknown",
                         settings=None, coords_spawns_known: bool = True, level: bool = False, calctype: str = "route",
                         use_s2: bool = False, s2_level: int = 15, joinqueue=None, include_event_id=None):

        if mode == WorkerType.RAID_MITM.value:
            route_manager = RouteManagerRaids(db_wrapper, dbm, area_id, max_radius,
                                              max_coords_within_radius,
                                              include_geofence, exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name,
                                              joinqueue=joinqueue,
                                              use_s2=use_s2, s2_level=s2_level
                                              )
        elif mode == WorkerType.MON_MITM.value:
            route_manager = RouteManagerMon(db_wrapper, dbm, area_id, max_radius,
                                            max_coords_within_radius,
                                            include_geofence, exclude_geofence, routefile,
                                            mode=mode, settings=settings, init=init, name=name,
                                            joinqueue=joinqueue,
                                            coords_spawns_known=coords_spawns_known,
                                            include_event_id=include_event_id
                                            )
        elif mode == WorkerType.IV_MITM.value:
            route_manager = RouteManagerIV(db_wrapper, dbm, area_id, 0, 99999999,
                                           include_geofence, exclude_geofence, routefile,
                                           mode=mode, settings=settings, init=False, name=name,
                                           joinqueue=joinqueue
                                           )
        elif mode == WorkerType.IDLE.value:
            route_manager = RouteManagerRaids(db_wrapper, dbm, area_id, max_radius,
                                              max_coords_within_radius,
                                              include_geofence, exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name,
                                              joinqueue=joinqueue
                                              )
        elif mode == WorkerType.STOPS.value:
            if level and calctype == 'route':
                route_manager = RouteManagerLeveling(db_wrapper, dbm, area_id, max_radius,
                                                     max_coords_within_radius,
                                                     include_geofence, exclude_geofence,
                                                     routefile,
                                                     mode=mode, settings=settings, init=init, name=name,
                                                     level=True,
                                                     calctype=calctype, joinqueue=joinqueue
                                                     )
            elif level and calctype == 'routefree':
                route_manager = RouteManagerLevelingRoutefree(db_wrapper, dbm, area_id, max_radius,
                                                              max_coords_within_radius,
                                                              include_geofence, exclude_geofence,
                                                              routefile,
                                                              mode=mode, settings=settings, init=init, name=name,
                                                              level=True,
                                                              calctype=calctype, joinqueue=joinqueue
                                                              )
            else:
                route_manager = RouteManagerQuests(db_wrapper, dbm, area_id, max_radius,
                                                   max_coords_within_radius,
                                                   include_geofence, exclude_geofence,
                                                   routefile,
                                                   mode=mode, settings=settings, init=init, name=name,
                                                   level=level,
                                                   calctype=calctype, joinqueue=joinqueue
                                                   )
        else:
            raise RuntimeError("Invalid mode found in mapping parser.")
        return route_manager
