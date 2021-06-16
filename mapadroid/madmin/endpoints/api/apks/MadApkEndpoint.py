import io
from threading import Thread
from typing import Optional
from zipfile import LargeZipFile, BadZipFile

from aiohttp import web
from loguru import logger

from mapadroid.db.helper.MadApkAutosearchHelper import MadApkAutosearchHelper
from mapadroid.mad_apk.apk_enums import APKArch, APKType
from mapadroid.mad_apk.custom_types import MADapks
from mapadroid.mad_apk.utils import convert_to_backend, get_apk_status
from mapadroid.mad_apk.wizard import APKWizard, WizardError, PackageImporter
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class MadApkEndpoint(AbstractMadminRootEndpoint):
    # TODO: Require auth
    async def get(self):
        apk_type_raw: str = self.request.match_info.get('apk_type')
        apk_arch_raw: str = self.request.match_info.get('apk_arch')
        apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        data = await get_apk_status(self._get_storage_obj())
        if apk_type is None and apk_arch is APKArch.noarch:
            return self._json_response(data=data)
        else:
            try:
                return self._json_response(data=data[apk_type][apk_arch])
            except KeyError:
                return self._json_response(data=data[apk_type])

    async def post(self):
        apk_type_raw: str = self.request.match_info.get('apk_type')
        apk_arch_raw: str = self.request.match_info.get('apk_arch')
        apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        is_upload: bool = False
        apk: Optional[io.BytesIO] = None
        filename: Optional[str] = None
        if self.request.content_type == 'multipart/form-data':
            # TODO: Use multipart properly? It appears we did not use request.form of flask either tho....
            # async for field in (await self.request.multipart()):
            # if field == "filename"
            json_data = await self.request.json()
            filename = json_data['data'].get('filename', None)
            try:
                apk = io.BytesIO(json_data['files'].get('file').read())
            except AttributeError:
                return self._json_response(text="No file present", status=406)
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
                # TODO: Add task and just run it without a thread
                thread_args = (apk_type, apk_arch)
                upload_thread = Thread(name='PackageWizard', target=wizard.apk_download, args=thread_args)
                upload_thread.start()
                return web.Response(status=204)
            elif call == 'search':
                await wizard.apk_search(apk_type, apk_arch)
                return web.Response(status=204)
            elif call == 'search_download':
                try:
                    await wizard.apk_all_actions()
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
            PackageImporter(apk_type, apk_arch, self._get_storage_obj(), apk, mimetype)
            if self.request.content_type == 'multipart/form-data':
                raise web.HTTPCreated()
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
