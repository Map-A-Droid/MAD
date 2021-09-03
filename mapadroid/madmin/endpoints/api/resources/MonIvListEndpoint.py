from typing import Dict, List, Optional, Set

from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.model import Base, SettingsMonivlist
from mapadroid.db.resource_definitions.MonIvList import MonIvList
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import (
    AbstractResourceEndpoint)


class MonIvListEndpoint(AbstractResourceEndpoint):
    async def _delete_connected_post(self, db_entry):
        pass

    def _attributes_to_ignore(self) -> Set[str]:
        return {"monlist_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsMonivlistHelper.get_mapped_lists(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return MonIvList.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsMonivlistHelper.get_entry(self._session, self._get_instance_id(), identifier)

    async def _create_instance(self, identifier):
        mon_iv_list = SettingsMonivlist()
        mon_iv_list.instance_id = self._get_instance_id()
        mon_iv_list.monlist_id = identifier
        return mon_iv_list

    async def _set_mon_ids_iv(self, iv_list: SettingsMonivlist, value: List[int]):
        await SettingsMonivlistHelper.set_mon_ids(self._session, iv_list.monlist_id, value)
        self._commit_trigger = True

    async def _get_additional_keys(self, identifier: int) -> Dict:
        additional_keys: Dict = {"mon_ids_iv": await SettingsMonivlistHelper.get_list(self._session,
                                                                                      self._get_instance_id(),
                                                                                      identifier)}
        return additional_keys

    async def _handle_additional_keys(self, db_entry: Base, key: str, value):
        if key == "mon_ids_iv":
            # Handle the list of IDs as those are stored in another table...
            await self._set_mon_ids_iv(db_entry, value)
            return True
        return False

    async def _delete_connected_prior(self, db_entry: SettingsMonivlist):
        await SettingsMonivlistHelper.delete_mapped_ids(self._session, db_entry.monlist_id)
