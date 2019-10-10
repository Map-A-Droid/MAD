from typing import Optional

from route.RouteManagerIV import RouteManagerIV
from route.RouteManagerMon import RouteManagerMon
from route.RouteManagerQuests import RouteManagerQuests
from route.RouteManagerRaids import RouteManagerRaids


class RouteManagerFactory:
    @staticmethod
    def get_routemanager(db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                         path_to_exclude_geofence: Optional[str], routefile: str, mode: Optional[str] = None,
                         init: bool = False, name: str = "unknown", settings=None, coords_spawns_known: bool = False,
                         level: bool = False, calctype: str = "optimized", joinqueue=None):
        if mode == "raids_mitm":
            route_manager = RouteManagerRaids(db_wrapper, coords, max_radius, max_coords_within_radius,
                                              path_to_include_geofence, path_to_exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue
                                              )
        elif mode == "mon_mitm":
            route_manager = RouteManagerMon(db_wrapper, coords, max_radius, max_coords_within_radius,
                                            path_to_include_geofence, path_to_exclude_geofence, routefile,
                                            mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue
                                            )
        elif mode == "iv_mitm":
            route_manager = RouteManagerIV(db_wrapper, coords, 0, 99999999,
                                           path_to_include_geofence, path_to_exclude_geofence, routefile,
                                           mode=mode, settings=settings, init=False, name=name, joinqueue=joinqueue
                                           )
        elif mode == "idle":
            route_manager = RouteManagerRaids(db_wrapper, coords, max_radius, max_coords_within_radius,
                                              path_to_include_geofence, path_to_exclude_geofence, routefile,
                                              mode=mode, settings=settings, init=init, name=name, joinqueue=joinqueue
                                              )
        elif mode == "pokestops":
            route_manager = RouteManagerQuests(db_wrapper, coords, max_radius, max_coords_within_radius,
                                               path_to_include_geofence, path_to_exclude_geofence, routefile,
                                               mode=mode, settings=settings, init=init, name=name, level=level,
                                               calctype=calctype, joinqueue=joinqueue
                                               )
        else:
            raise RuntimeError("Invalid mode found in mapping parser.")
        return route_manager
