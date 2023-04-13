from typing import Optional

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class DeleteLogEntryEndpoint(AbstractControlEndpoint):
    """
    "/delete_log_entry"
    """

    async def get(self):
        job_id: Optional[str] = self.request.query.get('id')

        if await self._get_device_updater().delete_log_id(job_id):
            await self._add_notice_message('Job deleted successfully')
        else:
            await self._add_notice_message('Job could not be deleted successfully')
        await self._redirect(self._url_for('install_status'))
