from typing import Optional

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import TrsStatus
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class DeleteStatusEntryEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/delete_status_entry"
    """

    # TODO: Auth
    # TODO: DELETE-method?
    async def get(self):
        device_id: Optional[int] = self._request.query.get("deviceid")
        status: Optional[TrsStatus] = await TrsStatusHelper.get(self._session, device_id)
        if status:
            await self._delete(status)
            return await self._json_response({'status': 'success'})
        else:
            return await self._json_response({'status': 'Unknown device ID'})
