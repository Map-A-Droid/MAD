from typing import Optional

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import TrsStatus
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class ResetStatusEntryEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/reset_status_entry"
    """

    # TODO: Auth
    # TODO: POST/PUT-method?
    async def get(self):
        device_id: Optional[int] = self._request.query.get("deviceid")
        status: Optional[TrsStatus] = await TrsStatusHelper.get(self._session, device_id)
        if status:
            await TrsStatusHelper.reset_status(self._session, self._get_instance_id(), device_id=device_id)
            return await self._json_response({'status': 'success'})
        else:
            return await self._json_response({'status': 'Unknown device ID'})
