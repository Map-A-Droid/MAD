from typing import Optional

from aiohttp_jinja2.helpers import url_for

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class DeleteLogEndpoint(AbstractControlEndpoint):
    """
    "/delete_log_entry"
    """

    # TODO: Auth
    async def get(self):
        job_id: Optional[str] = self.request.query.get('id')

        if await self._get_device_updater().delete_log_id(job_id):
            await self._add_notice_message('Job deleted successfully')
        else:
            await self._add_notice_message('Job could not be deleted successfully')
        await self._redirect(str(url_for('install_status')))
