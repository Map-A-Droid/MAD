from typing import Optional, Dict

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class GetWorkersEndpoint(AbstractControlEndpoint):
    """
    "/get_workers"
    """

    # TODO: Auth
    async def get(self):
        positions = []
        devicemappings: Optional[
            Dict[str, DeviceMappingsEntry]] = await self._get_mapping_manager().get_all_devicemappings()
        for name, device_mapping_entry in devicemappings.items():
            worker = {
                "name": name,
                "lat": device_mapping_entry.last_location.lat,
                "lon": device_mapping_entry.last_location.lng
            }
            positions.append(worker)
        del devicemappings
        resp = await self._json_response(positions)
        del positions
        return resp
