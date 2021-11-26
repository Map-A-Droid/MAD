import asyncio
import base64
import json
import os
import zipfile

from aiofile import async_open
from aiohttp import MultipartReader, web
from aiohttp.abc import Request
from loguru import logger
from werkzeug.utils import secure_filename

from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint


class UploadPluginEndpoint(AbstractPluginEndpoint):
    """
    "/upload_plugin"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def post(self):
        # check if the post request has the file part
        reader: MultipartReader = await self._request.multipart()
        file = await reader.next()
        # check if the post request has the file part
        if not file:
            await self._add_notice_message('No file part')
            raise web.HTTPFound(self._url_for("plugins"))
        elif not file.filename:
            await self._add_notice_message('No file selected for uploading (missing filename)')
            raise web.HTTPFound(self._url_for("plugins"))
        elif not self.__allowed_filename(file.filename):
            await self._add_notice_message('Allowed file type is ".mp" only!')
            raise web.HTTPFound(self._url_for("plugins"))
        filename = secure_filename(file.filename)
        # You cannot rely on Content-Length if transfer is chunked.
        size = 0
        async with async_open(os.path.join(self._get_mad_args().temp_path, filename), 'wb') as f:
            while True:
                chunk = await file.read_chunk()  # 8192 bytes by default.
                if not chunk:
                    break
                size += len(chunk)
                await f.write(chunk)

        if await self.__unzip_plugin(os.path.join(self._get_mad_args().temp_path, filename)):
            await self._add_notice_message('Plugin uploaded successfully - check plugin.ini and restart MAD now!')
        else:
            await self._add_notice_message('Error while installation - check MAD log.')
        raise web.HTTPFound(self._url_for("plugins"))

    async def __unzip_plugin(self, mpl_file):
        base = os.path.basename(mpl_file)
        plugin_tmp_zip = mpl_file + ".zip"
        logger.info("Try to install/update plugin: " + str(base))

        try:
            async with async_open(mpl_file, "r") as plugin_file:
                data = json.loads(await plugin_file.read())
        except (TypeError, ValueError):
            logger.error("Old or wrong plugin format - abort")
            return False
        else:
            pass

        plugin_content = base64.b64decode(data['plugin_content'])
        plugin_meta_name = data['plugin_name']
        plugin_version = data['plugin_version']

        async with async_open(plugin_tmp_zip, "wb") as tmp_plugin:
            await tmp_plugin.write(bytearray(plugin_content))

        extractpath = os.path.join(self._get_plugin_package(), plugin_meta_name)
        logger.debug("Plugin base path: " + str(base))
        logger.debug("Plugin extract path: " + str(extractpath))

        installed_version = None

        if os.path.isfile(extractpath + str("/version.mpl")):
            installed_version = self.get_plugin_version(str(extractpath))

        if installed_version is not None and plugin_version == installed_version:
            logger.warning("Plugin version already installed - abort")
            return False

        try:
            loop = asyncio.get_running_loop()
            # with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                None, self.__unzip, (extractpath, plugin_tmp_zip))

            os.remove(plugin_tmp_zip)

            # check for plugin.ini.example
            if not os.path.isfile(
                    os.path.join(extractpath, "plugin.ini.example")):
                logger.debug("Creating basic plugin.ini.example")
                async with async_open(os.path.join(extractpath, "plugin.ini.example"), 'w') as pluginini:
                    await pluginini.write('[plugin]\n')
                    await pluginini.write('active = false\n')
        except:  # noqa: E722 B001
            logger.opt(exception=True).error("Cannot install new plugin: " + str(mpl_file))
            return False

        logger.info("Installation successfully")
        return True

    def __unzip(self, extractpath, plugin_tmp_zip):
        with zipfile.ZipFile(plugin_tmp_zip, 'r') as zip_ref:
            zip_ref.extractall(extractpath)

    def __allowed_filename(self, filename) -> bool:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['mp']
