from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import get_coord_float
from mapadroid.route.RouteManagerBase import RoutePoolEntry


class GetRouteEndpoint(AbstractControlEndpoint):
    """
    "/get_route"
    """

    # TODO: Auth
    async def get(self):
        routeexport = []
        routemanager_names = await self._get_mapping_manager().get_all_routemanager_ids()
        for routemanager_name in routemanager_names:
            mode = self._get_mapping_manager().routemanager_get_mode(routemanager_name)
            name = self._get_mapping_manager().routemanager_get_name(routemanager_name)
            (route, workers) = await self._get_mapping_manager().routemanager_get_current_route(routemanager_name)

            if route is None:
                continue
            routeexport.append(GetRouteEndpoint.get_routepool_route(name, mode, route))
            if len(workers) > 1:
                for worker, worker_route in workers.items():
                    disp_name = '%s - %s' % (name, worker,)
                    routeexport.append(GetRouteEndpoint.get_routepool_route(disp_name, mode, worker_route))
        return self._json_response(routeexport)

    @staticmethod
    def get_routepool_route(name, mode, coords):
        parsed_coords = GetRouteEndpoint.get_routepool_coords(coords, mode)
        return {
            "name": name,
            "mode": mode,
            "coordinates": parsed_coords,
        }

    @staticmethod
    def get_routepool_coords(coord_list, mode):
        route_serialized = []
        prepared_coords = coord_list
        if isinstance(coord_list, RoutePoolEntry):
            prepared_coords = coord_list.subroute
        for location in prepared_coords:
            route_serialized.append([get_coord_float(location.lat), get_coord_float(location.lng)])
        return route_serialized
