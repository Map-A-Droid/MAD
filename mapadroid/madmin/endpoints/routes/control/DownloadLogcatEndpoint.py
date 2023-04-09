from typing import Optional

from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import generate_device_logcat_zip_path
from mapadroid.utils.functions import generate_path


class DownloadLogcatEndpoint(AbstractControlEndpoint):
    """
    "/download_logcat"
    """

    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        # origin_logger.info('MADmin: fetching logcat')

        filename = generate_device_logcat_zip_path(origin, self._get_mad_args())
        # origin_logger.info("Logcat being stored at {}", filename)
        if await self._fetch_logcat_websocket(origin, filename):
            attachment_filename = "logcat_{}.zip".format(origin)
            return web.FileResponse(generate_path(filename),
                                    headers={'Content-Disposition': f"Attachment; filename={attachment_filename}"})
        else:
            # origin_logger.error("Failed fetching logcat")
            # TODO: Return proper error :P
            return web.Response(text="Failed fetching logcat.")

    async def _fetch_logcat_websocket(self, origin: str, path_to_store_logcat_at: str) -> bool:
        temp_comm = self._get_ws_server().get_origin_communicator(origin)
        if not temp_comm:
            return False
        return await temp_comm.get_compressed_logcat(path_to_store_logcat_at)
