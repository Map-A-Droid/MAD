from typing import Dict, Optional, Set

from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import Base, SettingsRoutecalc
from mapadroid.db.resource_definitions.Routecalc import Routecalc
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class RoutecalcEndpoint(AbstractResourceEndpoint):
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
