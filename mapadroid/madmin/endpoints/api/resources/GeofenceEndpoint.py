from typing import Dict, Optional, Set, List

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsGeofenceHelper import SettingsGeofenceHelper
from mapadroid.db.model import Base, SettingsGeofence, SettingsArea
from mapadroid.db.resource_definitions.Geofence import Geofence
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class GeofenceEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsGeofence) -> Optional[Dict[int, str]]:
        db_wrapper: DbWrapper = self._get_db_wrapper()
        areas: Dict[int, SettingsArea] = await db_wrapper.get_all_areas(self._session)
        areas_with_geofence: List[SettingsArea] = []
        for area_id, area in areas.items():
            geofence_included = getattr(area, "geofence_included")
            geofence_excluded = getattr(area, "geofence_excluded")
            if (geofence_included and geofence_included == db_entry.geofence_id
                    or geofence_excluded and geofence_excluded == db_entry.geofence_id):
                areas_with_geofence.append(area)

        if not areas_with_geofence:
            return None
        else:
            mapped: Dict[int, str] = {area.area_id: str(area.name) for area in areas_with_geofence}
            return mapped

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
        pass

    async def _handle_additional_keys(self, db_entry: SettingsGeofence, key: str, value) -> bool:
        if key == "fence_data_raw" or key == "fence_data":
            to_be_written = str(value).replace("\'", "\"")
            db_entry.fence_data = to_be_written
            return True
        return False

    def _attributes_to_ignore(self) -> Set[str]:
        return {"geofence_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsGeofenceHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Geofence.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        geofence: Optional[SettingsGeofence] = await SettingsGeofenceHelper.get(self._session, self._get_instance_id(),
                                                                                identifier)
        return geofence

    async def _create_instance(self, identifier):
        geofence = SettingsGeofence()
        geofence.instance_id = self._get_instance_id()
        geofence.geofence_id = identifier
        return geofence
