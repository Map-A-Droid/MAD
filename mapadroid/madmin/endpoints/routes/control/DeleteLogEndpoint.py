from typing import Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class DeleteLogEndpoint(AbstractControlEndpoint):
    """
    "/delete_log"
    """

    # TODO: Auth
    async def get(self):
        only_success: Optional[str] = self.request.query.get('only_success')

        await self._get_device_updater().delete_log(only_success=only_success and only_success.lower() == "true")
        await self._redirect(self._url_for('install_status'))
