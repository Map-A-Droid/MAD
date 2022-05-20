from loguru import logger

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class ReloadJobsEndpoint(AbstractControlEndpoint):
    """
    "/reload_jobs"
    """

    # TODO: Auth
    async def get(self):
        logger.info("Reload existing jobs")
        await self._get_device_updater().stop_updater()
        await self._get_device_updater().start_updater()
        await self._redirect(self._url_for('uploaded_files'))
