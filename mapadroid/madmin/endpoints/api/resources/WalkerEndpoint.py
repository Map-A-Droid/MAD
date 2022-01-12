from typing import Dict, List, Optional, Set

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.helper.SettingsWalkerToWalkerareaHelper import \
    SettingsWalkerToWalkerareaHelper
from mapadroid.db.helper.SettingsWalkerareaHelper import SettingsWalkerareaHelper
from mapadroid.db.model import Base, SettingsWalker, SettingsWalkerToWalkerarea, SettingsDevice, SettingsWalkerarea
from mapadroid.db.resource_definitions.Walker import Walker
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class WalkerEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsWalker) -> Optional[Dict[int, str]]:
        assigned_to_walker: List[SettingsDevice] = await SettingsDeviceHelper.get_all_assigned_to_walker(self._session,
                                                                                                         db_entry)
        if not assigned_to_walker:
            return None
        else:
            names_of_devices: Dict[int, str] = {device.device_id: device.name for device in assigned_to_walker}
            return names_of_devices

    async def _delete_connected_prior(self, db_entry):
        all_walkerareas_mapped: Optional[List[SettingsWalkerToWalkerarea]] = await SettingsWalkerToWalkerareaHelper \
            .get(self._session, self._get_instance_id(), db_entry.walker_id)
        walkerarea_ids: List[int] = []
        if all_walkerareas_mapped:
            for walkerarea_mapped in all_walkerareas_mapped:
                walkerarea_ids.append(walkerarea_mapped.walkerarea_id)
                await self._session.delete(walkerarea_mapped)
        # Delete all SettingsWalkerarea entries....
        walkerareas: Dict[int, SettingsWalkerarea] = await SettingsWalkerareaHelper.get_all_mapped(
            self._session, self._get_instance_id())
        if walkerareas:
            for walkerarea_id in walkerarea_ids:
                if walkerarea_id in walkerareas:
                    await self._session.delete(walkerareas.get(walkerarea_id))

    async def _delete_connected_post(self, db_entry):
        pass

    def _attributes_to_ignore(self) -> Set[str]:
        return {"walker_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsWalkerHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Walker.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsWalkerHelper.get(self._session, self._get_instance_id(), identifier)

    async def _create_instance(self, identifier):
        routecalc: SettingsWalker = SettingsWalker()
        routecalc.instance_id = self._get_instance_id()
        routecalc.walker_id = identifier
        return routecalc

    async def _set_walkerareas(self, walker: SettingsWalker, value: List[int]):
        # TODO: Validate walkerarea_ids?
        await SettingsWalkerToWalkerareaHelper.set(self._session, walker, value)

    async def _get_additional_keys(self, identifier: int) -> Dict:
        setup: Optional[List[SettingsWalkerToWalkerarea]] = await SettingsWalkerToWalkerareaHelper.get(self._session,
                                                                                                       self._get_instance_id(),
                                                                                                       identifier)
        additional_keys: Dict = {"setup": setup}
        return additional_keys

    async def _handle_additional_keys(self, db_entry: Base, key: str, value) -> bool:
        if key == "setup":
            # Handle the list of IDs as those are stored in another table...
            await self._set_walkerareas(db_entry, value)
            return True
        return False
