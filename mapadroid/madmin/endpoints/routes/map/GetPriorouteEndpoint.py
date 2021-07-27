from typing import List, Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import get_coord_float
from mapadroid.route.prioq.AbstractRoutePriorityQueueStrategy import RoutePriorityQueueEntry
from mapadroid.utils.collections import Location


class GetPriorouteEndpoint(AbstractControlEndpoint):
    """
    "/get_prioroute"
    """

    # TODO: Auth
    async def get(self):
        routeexport = []
        routemanager_ids: List[int] = await self._get_mapping_manager().get_all_routemanager_ids()
        for routemanager_id in routemanager_ids:
            mode = await self._get_mapping_manager().routemanager_get_mode(routemanager_id)
            name = await self._get_mapping_manager().routemanager_get_name(routemanager_id)
            route: Optional[List[RoutePriorityQueueEntry]] = await self._get_mapping_manager().routemanager_get_current_prioroute(
                routemanager_id)

            if route is None:
                continue
            route_serialized = []

            for entry in route:
                route_serialized.append({
                    "timestamp": entry.timestamp_due,
                    "latitude": get_coord_float(entry.location.lat),
                    "longitude": get_coord_float(entry.location.lng)
                })

            routeexport.append({
                "name": name,
                "mode": mode,
                "coordinates": route_serialized
            })
        return await self._json_response(routeexport)
