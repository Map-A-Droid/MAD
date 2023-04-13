from typing import Dict, Optional

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import \
    check_authorization_header
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import get_geofences
from mapadroid.mapping_manager.MappingManager import AreaEntry


class GetAreasEndpoint(AbstractControlEndpoint):
    """
    "/get_areas"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        areas: Optional[Dict[int, AreaEntry]] = await self._get_mapping_manager().get_areas()
        areas_sorted = sorted(areas, key=lambda x: areas[x].settings.name)
        geofences = await get_geofences(self._get_mapping_manager())
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
