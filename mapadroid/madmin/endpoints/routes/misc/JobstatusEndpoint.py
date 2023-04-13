from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import \
    check_authorization_header
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import \
    AbstractStatisticsRootEndpoint


class JobstatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/jobstatus"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        return await self._json_response(self._get_mapping_manager().get_jobstatus())
