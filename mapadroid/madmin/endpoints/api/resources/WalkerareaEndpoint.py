from typing import Dict, Optional, Set, List

from mapadroid.db.helper.SettingsWalkerToWalkerareaHelper import SettingsWalkerToWalkerareaHelper
from mapadroid.db.helper.SettingsWalkerareaHelper import \
    SettingsWalkerareaHelper
from mapadroid.db.model import (Base, SettingsWalkerarea, SettingsWalkerToWalkerarea)
from mapadroid.db.resource_definitions.Walkerarea import Walkerarea
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class WalkerareaEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsWalkerarea) -> Optional[Dict[int, str]]:
        assigned_to_walkerarea: List[
            SettingsWalkerToWalkerarea] = await SettingsWalkerToWalkerareaHelper.get_all_of_walkerarea(self._session,
                                                                                                       db_entry)
        if not assigned_to_walkerarea:
            return None
        else:
            mapped: Dict[int, str] = {walker_to_walkerarea.walkerarea_id: str(walker_to_walkerarea.walker_id) for
                                      walker_to_walkerarea in assigned_to_walkerarea}
            return mapped

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
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

    async def _handle_additional_keys(self, db_entry: SettingsWalkerarea, key: str, value) -> bool:
        if key == "walker_id":
            # Make sure a SettingsWalkerToWalkerarea row is present, else create one to make sure a connection exists
            walkerarea_mappings_of_walker: List[SettingsWalkerToWalkerarea] = await SettingsWalkerToWalkerareaHelper \
                .get(self._session, self._get_instance_id(), value)
            if walkerarea_mappings_of_walker:
                walkerarea_mappings_of_walker.sort(key=lambda x: x.area_order)
                for walkerarea_mapping in walkerarea_mappings_of_walker:
                    if walkerarea_mapping.walkerarea_id == db_entry.walkerarea_id:
                        # already present, nothing to do
                        return True

            mapping: SettingsWalkerToWalkerarea = SettingsWalkerToWalkerarea()
            mapping.walkerarea_id = db_entry.walkerarea_id
            mapping.walker_id = value
            if walkerarea_mappings_of_walker:
                order = walkerarea_mappings_of_walker[-1].area_order + 1
            else:
                order = 0
            mapping.area_order = order
            self._save(mapping)
            return True
        return False
