from typing import Dict, Optional, Set, List

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import Base, SettingsRoutecalc, SettingsArea
from mapadroid.db.resource_definitions.Routecalc import Routecalc
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class RoutecalcEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsRoutecalc) -> Optional[Dict[int, str]]:
        db_wrapper: DbWrapper = self._get_db_wrapper()
        areas: Dict[int, SettingsArea] = await db_wrapper.get_all_areas(self._session)
        areas_with_routecalc: List[SettingsArea] = []
        for area_id, area in areas.values():
            routecalc_id: Optional[int] = getattr(area, "routecalc")
            if routecalc_id and routecalc_id == db_entry.routecalc_id:
                areas_with_routecalc.append(area)

        if not areas_with_routecalc:
            return None
        else:
            mapped: Dict[int, str] = {area.area_id: f"area {area.name} ({area.area_id}) is still connected to routecalc" for area in areas_with_routecalc}
            return mapped

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
        pass

    async def _handle_additional_keys(self, db_entry: SettingsRoutecalc, key: str, value) -> bool:
        if key == "routefile_raw" or key == "routefile":
            if not value:
                db_entry.routefile = "[]"
            else:
                to_be_written = str(value).replace("\'", "\"")
                db_entry.routefile = to_be_written
            return True
        return False

    def _attributes_to_ignore(self) -> Set[str]:
        return {"routecalc_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsRoutecalcHelper.get_all(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Routecalc.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsRoutecalcHelper.get(self._session, identifier)

    async def _create_instance(self, identifier):
        routecalc: SettingsRoutecalc = SettingsRoutecalc()
        routecalc.instance_id = self._get_instance_id()
        routecalc.routecalc_id = identifier
        return routecalc
