from typing import Dict, Optional, Set

from mapadroid.db.helper.SettingsDevicepoolHelper import \
    SettingsDevicepoolHelper
from mapadroid.db.model import Base, SettingsDevicepool
from mapadroid.db.resource_definitions.Devicepool import Devicepool
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class DevicepoolEndpoint(AbstractResourceEndpoint):
    def _attributes_to_ignore(self) -> Set[str]:
        return {"pool_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsDevicepoolHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Devicepool.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsDevicepoolHelper.get(self._session, identifier)

    async def _create_instance(self, identifier) -> Base:
        pool: SettingsDevicepool = SettingsDevicepool()
        pool.instance_id = self._get_instance_id()
        pool.pool_id = identifier
        return pool
