import asyncio
import io
from typing import Optional
from zipfile import LargeZipFile, BadZipFile

from aiohttp import MultipartReader, web
from loguru import logger
from werkzeug.utils import secure_filename

from mapadroid.db.helper.MadApkAutosearchHelper import MadApkAutosearchHelper
from mapadroid.mad_apk.apk_enums import APKArch, APKType
from mapadroid.mad_apk.custom_types import MADapks
from mapadroid.mad_apk.utils import convert_to_backend, get_apk_status
from mapadroid.mad_apk.wizard import APKWizard, WizardError, PackageImporter
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import allowed_file


class MadApkEndpoint(AbstractMadminRootEndpoint):
    # TODO: Require auth
    async def get(self):
        apk_type_raw: str = self.request.match_info.get('apk_type')
        apk_arch_raw: str = self.request.match_info.get('apk_arch')
        apk_type = None
        apk_arch = APKArch.noarch
        if apk_type_raw == "reload":
            await self._get_storage_obj().reload()
        else:
            apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        data = await get_apk_status(self._get_storage_obj())
        if apk_type is None and apk_arch is APKArch.noarch:
            return await self._json_response(data=data)
        else:
            try:
                return await self._json_response(data=data[apk_type][apk_arch])
            except KeyError:
                return await self._json_response(data=data[apk_type])

    async def post(self):
        apk_type_raw: str = self.request.match_info.get('apk_type')
        apk_arch_raw: str = self.request.match_info.get('apk_arch')
        apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        is_upload: bool = False
        apk: Optional[io.BytesIO] = None
        filename: Optional[str] = None

        if self.request.content_type == 'multipart/form-data':
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

            try:
                apk = io.BytesIO(await file.read())
            except AttributeError:
                return await self._json_response(text="No file present", status=406)
            is_upload = True
        elif self.request.content_type == 'application/octet-stream':
            filename = self.request.headers.get('filename')
            # TODO: use await self.request.multipart() ?
            apk = io.BytesIO(await self.request.read())
            is_upload = True
        if is_upload:
            return await self.handle_file_upload(apk, apk_arch, apk_type, filename)
        else:
            return await self.handle_wizard_directive(apk_arch, apk_type)

    async def handle_wizard_directive(self, apk_arch: Optional[APKArch], apk_type: Optional[APKType]) -> web.Response:
        try:
            json_data = await self.request.json()
            call = json_data['call']
            wizard = APKWizard(self._get_db_wrapper(), self._get_storage_obj())
            if call == 'import':
                loop = asyncio.get_running_loop()
                loop.create_task(wizard.apk_download(apk_type, apk_arch))
                return web.Response(status=204)
            elif call == 'search':
                try:
                    await wizard.apk_search(apk_type, apk_arch)
                except ValueError as e:
                    logger.exception(e)
                    raise web.HTTPNotFound
                return web.Response(status=204)
            elif call == 'search_download':
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(wizard.apk_nonblocking_download())
                    return web.Response(status=204)
                except TypeError:
                    return web.Response(status=404)
            else:
                return web.Response(text=call, status=501)
        except KeyError:
            import traceback
            traceback.print_exc()
            return web.Response(text="Unknown call.", status=400)

    async def handle_file_upload(self, apk: io.BytesIO, apk_arch: Optional[APKArch],
                                 apk_type: Optional[APKType], filename: Optional[str]) -> web.Response:
        if filename is None:
            return web.Response(text="Filename must be specified", status=406)
        elems: MADapks = await get_apk_status(self._get_storage_obj())
        try:
            elems[apk_type][apk_arch]
        except KeyError:
            return web.Response(text="Non-supported Type / Architecture", status=406)
        filename_split = filename.rsplit('.', 1)
        if filename_split[1] in ['zip', 'apks']:
            mimetype = 'application/zip'
        elif filename_split[1] == 'apk':
            mimetype = 'application/vnd.android.package-archive'
        else:
            return web.Response(text="Unsupported extension", status=406)
        try:
            package_importer: PackageImporter = PackageImporter(apk_type, apk_arch, self._get_storage_obj(),
                                                                apk, mimetype)
            await package_importer.import_configured()
            return web.Response(status=201)
        except (BadZipFile, LargeZipFile) as err:
            return web.Response(text=str(err), status=406)
        except WizardError as err:
            logger.warning(err)
            return web.Response(text=str(err), status=406)
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred!")
            return web.Response(status=500)

    async def delete(self):
        apk_type_raw: str = self.request.match_info.get('apk_type')
        apk_arch_raw: str = self.request.match_info.get('apk_arch')
        apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        if apk_type is None:
            raise web.HTTPNotFound()
        if await self._get_storage_obj().delete_file(apk_type, apk_arch):
            await MadApkAutosearchHelper.delete(self._session, apk_type, apk_arch)
            raise web.HTTPAccepted()
        raise web.HTTPNotFound()
