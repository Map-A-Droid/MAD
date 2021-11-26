from typing import Dict, Optional, Set, List

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsDevicepoolHelper import \
    SettingsDevicepoolHelper
from mapadroid.db.model import Base, SettingsDevicepool, SettingsDevice
from mapadroid.db.resource_definitions.Devicepool import Devicepool
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class DevicepoolEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsDevicepool) -> Optional[Dict[int, str]]:
        assigned_to_pool: List[SettingsDevice] = await SettingsDeviceHelper.get_assigned_to_pool(self._session,
                                                                                                 db_entry)
        if not assigned_to_pool:
            return None
        else:
            mapped: Dict[int, str] = {device.device_id: f"Device {device.name} is still assigned" for device in
                                      assigned_to_pool}
            return mapped

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
        pass

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
