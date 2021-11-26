import asyncio
from typing import List, Dict

from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import SettingsRoutecalc
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import get_coord_float
from mapadroid.route.RouteManagerBase import RoutePoolEntry
from mapadroid.route.routecalc.RoutecalcUtil import RoutecalcUtil
from mapadroid.utils.collections import Location


class GetRouteEndpoint(AbstractControlEndpoint):
    """
    "/get_route"
    """

    # TODO: Auth
    async def get(self):
        routeinfo_by_id = {}

        routemanager_ids: List[int] = await self._get_mapping_manager().get_all_routemanager_ids()
        for routemanager_id in routemanager_ids:
            (route, workers) = await self._get_mapping_manager().routemanager_get_current_route(routemanager_id)
            if route is None:
                continue

            mode = await self._get_mapping_manager().routemanager_get_mode(routemanager_id)
            name = await self._get_mapping_manager().routemanager_get_name(routemanager_id)
            routecalc_id = await self._get_mapping_manager().routemanager_get_routecalc_id(routemanager_id)
            routeinfo_by_id[routecalc_id] = routeinfo = {
                "id": routecalc_id,
                "route": route,
                "name": name,
                "mode": mode,
                "subroutes": []
            }

            if len(workers) > 1:
                for worker, worker_route in workers.items():
                    routeinfo["subroutes"].append({
                        "id": "%d_sub_%s" % (routecalc_id, worker),
                        "route": worker_route,
                        "name": "%s - %s" % (routeinfo["name"], worker),
                        "tag": "subroute"
                    })

        if len(routeinfo_by_id) > 0:
            routecalcs: Dict[int, SettingsRoutecalc] = await SettingsRoutecalcHelper \
                .get_all(self._session, self._get_instance_id())
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self.__serialize_routecalcs, routecalcs, routeinfo_by_id)
            del routecalcs
            data = await loop.run_in_executor(
                None, self.__prepare_data, routeinfo_by_id)
            del routeinfo_by_id
        else:
            data = []
        resp = await self._json_response(data)
        del data
        return resp

    def __prepare_data(self, routeinfo_by_id):
        data = list(map(lambda r: self.get_routepool_route(r), routeinfo_by_id.values()))
        return data

    @staticmethod
    def __serialize_routecalcs(routecalcs, routeinfo_by_id):
        for routecalc_id, routecalc in routecalcs.items():
            if routecalc_id in routeinfo_by_id:
                routeinfo = routeinfo_by_id[routecalc_id]
                db_route = list(map(lambda coord: Location(coord["lat"], coord["lng"]),
                                    RoutecalcUtil.read_saved_json_route(routecalc)))
                if db_route != routeinfo["route"]:
                    routeinfo["subroutes"].append({
                        "id": "%d_unapplied" % routeinfo["id"],
                        "route": db_route,
                        "name": "%s (unapplied)" % routeinfo["name"],
                        "tag": "unapplied"
                    })

    @staticmethod
    def get_routepool_route(route):
        return {
            "id": route["id"],
            "name": route["name"],
            "mode": route["mode"],
            "coordinates": GetRouteEndpoint.get_routepool_coords(route["route"]),
            "subroutes": list(map(lambda subroute: {
                "id": subroute["id"],
                "name": subroute["name"],
                "tag": subroute["tag"],
                "coordinates": GetRouteEndpoint.get_routepool_coords(subroute["route"])
            }, route["subroutes"]))
        }

    @staticmethod
    def get_routepool_coords(coord_list):
        route_serialized = []
        prepared_coords = coord_list
        if isinstance(coord_list, RoutePoolEntry):
            prepared_coords = coord_list.subroute
        for location in prepared_coords:
            route_serialized.append([get_coord_float(location.lat), get_coord_float(location.lng)])
        return route_serialized
