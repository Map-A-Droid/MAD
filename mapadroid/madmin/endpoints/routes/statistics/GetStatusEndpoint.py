from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class GetStatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_status"
    """

    # TODO: Auth
    async def get(self):
        stats = await TrsStatusHelper.get_all_of_instance(self._session, self._get_instance_id())
        return self._json_response(stats)
