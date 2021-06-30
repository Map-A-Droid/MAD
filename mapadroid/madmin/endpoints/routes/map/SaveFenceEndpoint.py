from typing import Optional

from mapadroid.db.helper.SettingsGeofenceHelper import SettingsGeofenceHelper
from mapadroid.db.model import SettingsGeofence
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class SaveFenceEndpoint(AbstractMadminRootEndpoint):
    """
    "/savefence"
    """

    # TODO: Auth
    async def post(self):
        name: Optional[str] = self._request.query.get("name")
        coords: Optional[str] = self._request.query.get("coords")

        if not name and not coords:
            await self._redirect(self._url_for("map"))

        # Enforce 128 character limit
        if len(name) > 128:
            name = name[len(name) - 128:]
        geofence: Optional[SettingsGeofence] = await SettingsGeofenceHelper.get_by_name(self._session,
                                                                                        self._get_instance_id(),
                                                                                        name)
        if not geofence:
            geofence = SettingsGeofence()
            geofence.name = name
        geofence.fence_type = "polygon"
        geofence.fence_data = coords.split("|")
        try:
            await self._save(geofence)
        except Exception:
            # TODO - present the user with an issue.  probably fence-name already exists
            pass
        await self._redirect(self._url_for("map"), commit=True)
