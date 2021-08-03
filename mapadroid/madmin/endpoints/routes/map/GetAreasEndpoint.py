from typing import Dict, Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import get_geofences
from mapadroid.mapping_manager.MappingManager import AreaEntry


class GetAreasEndpoint(AbstractControlEndpoint):
    """
    "/get_areas"
    """

    # TODO: Auth
    async def get(self):
        areas: Optional[Dict[int, AreaEntry]] = await self._get_mapping_manager().get_areas()
        areas_sorted = sorted(areas, key=lambda x: areas[x].settings.name)
        geofences = await get_geofences(self._get_mapping_manager(), self._session, self._get_instance_id())
        geofencexport = []
        for area_id in areas_sorted:
            fences = geofences[area_id]
            coordinates = []
            for fname, coords in fences.get('include').items():
                coordinates.append([coords, fences.get('exclude').get(fname, [])])
            geofencexport.append({'name': areas[area_id].settings.name, 'coordinates': coordinates})
        del geofences
        resp = await self._json_response(geofencexport)
        del geofencexport
        return resp
