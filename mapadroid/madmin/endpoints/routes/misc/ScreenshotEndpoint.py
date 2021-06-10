import os

from aiofile import async_open
from aiohttp import streamer, web

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.utils.functions import generate_path


class ScreenshotEndpoint(AbstractRootEndpoint):
    """
    "/screenshot/{path}"
    """

    # TODO: Auth
    async def get(self):
        # TODO: Validate screenshot, otherwise we might be sending whatever....
        file_name = self.request.match_info['path']
        madmin_thumbnail = self.request.query.get("madmin")
        if madmin_thumbnail:
            file_name = "madmin/" + file_name
        headers = {
            "Content-disposition": "attachment; filename={file_name}".format(file_name=file_name)
        }

        file_path = os.path.join(generate_path(self._get_mad_args().temp_path), file_name)

        if not os.path.exists(file_path):
            return web.Response(
                body='File <{file_name}> does not exist'.format(file_name=file_name),
                status=404
            )
        else:
            return web.FileResponse(
                path=file_path,
                headers=headers
            )

    @streamer
    async def file_sender(self, writer, file_path=None):
        """
        This function will read large file chunk by chunk and send it through HTTP
        without reading them into memory
        """
        # TODO: Asyncio
        async with async_open(file_path, 'rb') as f:
            chunk = await f.read(2 ** 16)
            while chunk:
                await writer.write(chunk)
                chunk = await f.read(2 ** 16)
