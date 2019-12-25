from typing import Optional

from route.RouteManagerIV import RouteManagerIV
from route.RouteManagerMon import RouteManagerMon
from route.RouteManagerQuests import RouteManagerQuests
from route.RouteManagerRaids import RouteManagerRaids
from route.RouteManagerLeveling import RouteManagerLeveling

class RouteManagerFactory:
    @staticmethod
    def get_routemanager(db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                         path_to_exclude_geofence: Optional[int], routefile: str, mode: Optional[str] = None,
                         init: bool = False, name: str = "unknown", settings=None, coords_spawns_known: bool = False,
                         level: bool = False, calctype: str = "optimized", useS2: bool = False, S2level: int = 15, joinqueue=None):

        if mode == "raids_mitm":
            route_manager = RouteManagerRaids(db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius,
                                              path_to_include_geofence, path_to_exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue,
                                              useS2=useS2, S2level=S2level
                                              )
        elif mode == "mon_mitm":
            route_manager = RouteManagerMon(db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius,
                                            path_to_include_geofence, path_to_exclude_geofence, routefile,
                                            mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue,
                                            coords_spawns_known=coords_spawns_known
                                            )
        elif mode == "iv_mitm":
            route_manager = RouteManagerIV(db_wrapper, dbm, area_id, coords, 0, 99999999,
                                           path_to_include_geofence, path_to_exclude_geofence, routefile,
                                           mode=mode, settings=settings, init=False, name=name, joinqueue=joinqueue
                                           )
        elif mode == "idle":
            route_manager = RouteManagerRaids(db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius,
                                              path_to_include_geofence, path_to_exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue
                                              )
        elif mode == "pokestops":
            if level:
                route_manager = RouteManagerLeveling(db_wrapper,  dbm, area_id, coords, max_radius, max_coords_within_radius,
                                                     path_to_include_geofence, path_to_exclude_geofence, routefile,
                                                     mode=mode, settings=settings, init=init, name=name, level=True,
                                                     calctype=calctype, joinqueue=joinqueue
                                                     )
            else:
                route_manager = RouteManagerQuests(db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius,
                                               path_to_include_geofence, path_to_exclude_geofence, routefile,
                                               mode=mode, settings=settings, init=init, name=name, level=level,
                                               calctype=calctype, joinqueue=joinqueue
                                               )
        else:
            raise RuntimeError("Invalid mode found in mapping parser.")
        return route_manager

