from typing import Optional, Dict

from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import TrsSpawn, TrsStatus
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
            self._delete(status)
            return self._json_response({'status': 'success'})
        else:
            return self._json_response({'status': 'Unknown device ID'})
