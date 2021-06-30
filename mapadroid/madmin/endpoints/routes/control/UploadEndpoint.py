import os

import aiohttp_jinja2
from aiofile import async_open
from aiohttp import MultipartReader, web
from werkzeug.utils import secure_filename

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import allowed_file


class UploadEndpoint(AbstractControlEndpoint):
    """
    "/upload"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('upload.html')
    async def get(self):
        return {"header": "File Upload", "title": "File Upload"}

    # TODO: Auth
    async def post(self):
        reader: MultipartReader = await self._request.multipart()
        file = await reader.next()
        # check if the post request has the file part
        if not file:
            await self._add_notice_message('No file part')
            raise web.HTTPFound(self._url_for("upload"))
        elif not file.filename:
            await self._add_notice_message('No file selected for uploading')
            raise web.HTTPFound(self._url_for("upload"))
        elif not allowed_file(file.filename):
            await self._add_notice_message('Allowed file type is apk only!')
            raise web.HTTPFound(self._url_for("upload"))
        filename = secure_filename(file.filename)
        # You cannot rely on Content-Length if transfer is chunked.
        size = 0
        async with async_open(os.path.join(self._get_mad_args().upload_path, filename), 'wb') as f:
            while True:
                chunk = await file.read_chunk()  # 8192 bytes by default.
                if not chunk:
                    break
                size += len(chunk)
                await f.write(chunk)

        await self._add_notice_message('File uploaded successfully')
        raise web.HTTPFound(self._url_for("uploaded_files"))
