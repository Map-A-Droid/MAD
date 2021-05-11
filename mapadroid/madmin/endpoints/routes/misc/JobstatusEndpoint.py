from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class JobstatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/jobstatus"
    """

    # TODO: Auth
    async def get(self):
        return self._json_response(self._get_mapping_manager().get_jobstatus())
