from typing import Dict, Optional, Set

from mapadroid.db.helper.SettingsWalkerareaHelper import \
    SettingsWalkerareaHelper
from mapadroid.db.model import (Base, SettingsWalkerarea)
from mapadroid.db.resource_definitions.Walkerarea import Walkerarea
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class WalkerareaEndpoint(AbstractResourceEndpoint):
    async def _delete_connected(self, db_entry):
        pass

    def _attributes_to_ignore(self) -> Set[str]:
        return {"walkerarea_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsWalkerareaHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Walkerarea.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsWalkerareaHelper.get(self._session, self._get_instance_id(), identifier)

    async def _create_instance(self, identifier) -> Base:
        walkerarea: SettingsWalkerarea = SettingsWalkerarea()
        walkerarea.instance_id = self._get_instance_id()
        walkerarea.walkerarea_id = identifier
        return walkerarea
