from typing import Optional, Dict, Set, List

from aiohttp import web
from sqlalchemy import Column

from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.helper.SettingsWalkerToWalkerareaHelper import SettingsWalkerToWalkerareaHelper
from mapadroid.db.model import Base, SettingsWalker
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import AbstractResourceEndpoint, \
    DataHandlingMethodology


class WalkerEndpoint(AbstractResourceEndpoint):
    # TODO: Needs to handle walkerareas accordingly in get and update similar to monivlist...
    #
    def _attributes_to_ignore(self) -> Set[str]:
        return {"walker_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsWalkerHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self) -> Dict:
        # TODO...
        return {}

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
        additional_keys: Dict = {"setup": await SettingsWalkerToWalkerareaHelper.get(self._session,
                                                                                     self._get_instance_id(),
                                                                                     identifier)}
        return additional_keys

    async def _handle_additional_keys(self, db_entry: Base, key: str, value):
        if key == "setup":
            # Handle the list of IDs as those are stored in another table...
            await self._set_walkerareas(db_entry, value)
