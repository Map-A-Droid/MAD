from typing import Optional, Dict

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import SettingsArea
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.worker.WorkerType import WorkerType


class GetStatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_status"
    """

    # TODO: Auth
    async def get(self):
        stats = await TrsStatusHelper.get_all_of_instance(self._session, self._get_instance_id())
        areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)
        serialized = []
        for stat in stats:
            stat_serialized = {var: val for var, val in vars(stat).items() if not var.startswith("_")}
            routemanager_id_device_is_using: Optional[int] = await self._get_mapping_manager().get_routemanager_id_where_device_is_registered(stat.name)
            if routemanager_id_device_is_using:
                # append routemanager name, routemanager mode and area id...
                stat_serialized["rmname"] = await self._get_mapping_manager().routemanager_get_name(routemanager_id_device_is_using)
                stat_serialized["mode"] = (await self._get_mapping_manager().routemanager_get_mode(routemanager_id_device_is_using)).value
            else:
                stat_serialized["rmname"] = areas.get(stat.area_id).name
                stat_serialized["mode"] = areas.get(stat.area_id).mode

            stat_serialized["area_id"] = stat.area_id
            serialized.append(stat_serialized)
        return self._json_response(serialized)
