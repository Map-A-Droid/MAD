import asyncio
import base64
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from aiofile import async_open
from aiohttp import web
from aiohttp.abc import Request
from loguru import logger

from mapadroid.plugins.endpoints.AbstractPluginEndpoint import AbstractPluginEndpoint
from mapadroid.utils.functions import generate_path


class DownloadPluginEndpoint(AbstractPluginEndpoint):
    """
    "/download_plugin"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        plugin: Optional[str] = self.request.query.get('plugin')
        if plugin is None:
            raise web.HTTPFound(self._url_for("plugins"))

        mad_plugin = next((item for item in self._get_plugins() if item["name"] == plugin), None)
        if mad_plugin is None:
            raise web.HTTPFound(self._url_for("plugins"))

        mp_file = await self.__zip_plugin(plugin, mad_plugin['path'], self.get_plugin_version(mad_plugin['path']))
        if mp_file is None:
            raise web.HTTPFound(self._url_for("plugins"))
        filename = plugin + ".mp"
        return web.FileResponse(generate_path(self._get_mad_args().temp_path) + "/" + filename,
                                headers={'Content-Disposition': f"Attachment; filename={filename}"})

    async def __zip_plugin(self, plugin_name, folder, version):
        plugin_file_temp = os.path.join(self._get_mad_args().temp_path, str(plugin_name) + '.tmp')
        plugin_file = os.path.join(self._get_mad_args().temp_path, str(plugin_name) + '.mp')
        if not os.path.isdir(folder):
            logger.error("Plugin folder does not exists - abort")
            return None

        if os.path.isfile(plugin_file):
            os.remove(plugin_file)

        if os.path.isfile(plugin_file_temp):
            os.remove(plugin_file_temp)

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                pool, self.__zip, (folder, plugin_file_temp))

        async with async_open(plugin_file_temp, mode='rb') as plugin_zip:
            plugin_contents = await plugin_zip.read()

        plugin_dict = {"plugin_name": plugin_name, "plugin_content": base64.b64encode(plugin_contents).decode('utf-8'),
                       "plugin_version": version}

        async with async_open(plugin_file, 'w') as plugin_export:
            await plugin_export.write(json.dumps(plugin_dict))

        os.remove(plugin_file_temp)

        return plugin_file

    def __zip(self, folder, plugin_file_temp):
        with zipfile.ZipFile(plugin_file_temp, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            rootlen = len(folder) + 1
            for base, _, files in os.walk(folder):
                if "__pycache__" not in base and "/." not in base:
                    for file_to_zip in files:
                        if file_to_zip != "plugin.ini" and not file_to_zip.startswith("."):
                            fn = os.path.join(base, file_to_zip)
                            zip_file.write(fn, fn[rootlen:])
