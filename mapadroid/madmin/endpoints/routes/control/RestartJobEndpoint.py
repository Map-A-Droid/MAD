from typing import Optional

from aiohttp_jinja2.helpers import url_for

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class RestartJobEndpoint(AbstractControlEndpoint):
    """
    "/restart_job"
    """

    # TODO: Auth
    # TODO: Also "post"?
    # TODO: nocache?
    async def get(self):
        job_id_raw: Optional[str] = self.request.query.get('id')
        if not job_id_raw:
            await self._add_notice_message('ID not specified - restart failed')

        await self._get_device_updater().restart_job(job_id_raw)
        await self._add_notice_message('Job requeued')
        await self._redirect(self._url_for('install_status'))
