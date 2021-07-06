from typing import Dict, Optional, Set

from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import Base, SettingsRoutecalc
from mapadroid.db.resource_definitions.Routecalc import Routecalc
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class RoutecalcEndpoint(AbstractResourceEndpoint):
    async def _delete_connected(self, db_entry):
        pass

    async def _handle_additional_keys(self, db_entry: SettingsRoutecalc, key: str, value) -> bool:
        if key == "routefile_raw" or key == "routefile":
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
