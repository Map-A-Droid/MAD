import io
from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.mad_apk import convert_to_backend, stream_package, APKArch, APKType, MADapks, get_apk_status, \
    PackageImporter, WizardError, BadZipFile, LargeZipFile, APKWizard
from mapadroid.madmin.RootEndpoint import RootEndpoint


class MadApkEndpoint(RootEndpoint):
    # TODO: Require auth
    async def get(self):
        pass

    async def post(self):
        apk_type_raw: str = self.request.match_info['apk_type']
        apk_arch_raw: str = self.request.match_info['apk_arch']
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
                # TODO: Return proper response...
                return ('No file present', 406)
            is_upload = True
        elif self.request.content_type == 'application/octet-stream':
            filename = self.request.headers.get('filename', None)
            # TODO: await self.request.multipart()
            apk = io.BytesIO(await self.request.read())
            is_upload = True
        if is_upload:
            return await self.handle_file_upload(apk, apk_arch, apk_type, filename)
        else:
            return await self.handle_wizard_directive(apk_arch, apk_type)

    async def handle_wizard_directive(self, apk_arch: Optional[APKArch], apk_type: Optional[APKType]):
        try:
            json_data = await self.request.json()
            call = json_data['call']
            wizard = APKWizard(self._get_db_wrapper(), self._get_storage_obj())
            if call == 'import':
                # TODO: Add task and just run it without a thread
                thread_args = (apk_type, apk_arch)
                upload_thread = Thread(name='PackageWizard', target=wizard.apk_download, args=thread_args)
                upload_thread.start()
                return (None, 204)
            elif call == 'search':
                wizard.apk_search(apk_type, apk_arch)
                return (None, 204)
            elif call == 'search_download':
                try:
                    wizard.apk_all_actions()
                    return (None, 204)
                except TypeError:
                    return (None, 404)
            else:
                return (call, 501)
        except KeyError:
            import traceback
            traceback.print_exc()
            return (call, 501)

    async def handle_file_upload(self, apk: io.BytesIO, apk_arch: Optional[APKArch],
                                 apk_type: Optional[APKType], filename: str):
        if filename is None:
            return ('filename must be specified', 406)
        elems: MADapks = get_apk_status(self._get_storage_obj())
        try:
            elems[apk_type][apk_arch]
        except KeyError:
            return ('Non-supported Type / Architecture', 406)
        filename_split = filename.rsplit('.', 1)
        if filename_split[1] in ['zip', 'apks']:
            mimetype = 'application/zip'
        elif filename_split[1] == 'apk':
            mimetype = 'application/vnd.android.package-archive'
        else:
            return ('Unsupported extension', 406)
        try:
            PackageImporter(apk_type, apk_arch, self._get_storage_obj(), apk, mimetype)
            if self.request.content_type == 'multipart/form-data':
                raise web.HTTPCreated()
            return (None, 201)
        except (BadZipFile, LargeZipFile) as err:
            return (str(err), 406)
        except WizardError as err:
            logger.warning(err)
            raise web.HTTPNotAcceptable()
            # TODO: Custom redirect/response with the message and code?
            # return (str(err), 406)
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred!")
            return (None, 500)

    async def delete(self):
        pass
