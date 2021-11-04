from typing import Optional, Dict, List

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import SettingsArea, TrsStatus, SettingsDevice
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class GetStatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_status"
    """

    # TODO: Auth
    async def get(self):
        stats: List[TrsStatus] = await TrsStatusHelper.get_all_of_instance(self._session, self._get_instance_id())
        settings_devices: Dict[int, SettingsDevice] = await SettingsDeviceHelper.get_all_mapped(self._session,
                                                                                                self._get_instance_id())
        areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)
        serialized = []
        for stat in stats:
            settings_of_device: Optional[SettingsDevice] = settings_devices.get(stat.device_id)
            if not settings_of_device:
                continue
            stat_serialized = {var: val for var, val in vars(stat).items() if not var.startswith("_")}
            settings_serialized = {var: val for var, val in vars(settings_of_device).items() if not var.startswith("_")}
            stat_serialized.update(settings_serialized)
            routemanager_id_device_is_using: Optional[
                int] = await self._get_mapping_manager().get_routemanager_id_where_device_is_registered(stat.device_id)
            if routemanager_id_device_is_using:
                # append routemanager name, routemanager mode and area id...
                stat_serialized["rmname"] = await self._get_mapping_manager().routemanager_get_name(
                    routemanager_id_device_is_using)
                stat_serialized["mode"] = (
                    await self._get_mapping_manager().routemanager_get_mode(routemanager_id_device_is_using)).value
            else:
                area: Optional[SettingsArea] = areas.get(stat.area_id)
                stat_serialized["rmname"] = area.name if area else None
                stat_serialized["mode"] = area.mode if area else None

            stat_serialized["area_id"] = stat.area_id

            serialized.append(stat_serialized)
        return await self._json_response(serialized)
