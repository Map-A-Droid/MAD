import os
from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class InstallFileEndpoint(AbstractControlEndpoint):
    """
    "/install_file"
    """

    @aiohttp_jinja2.template('uploaded_files.html')
    @expand_context()
    async def get(self):
        jobname: Optional[str] = self.request.query.get('jobname')
        origin: Optional[str] = self.request.query.get('origin')
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False
        job_type: Optional[str] = self.request.query.get('type')

        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            await self._add_notice_message("Unknown device")
            await self._redirect(self._url_for('uploaded_files'))
        if useadb and os.path.exists(os.path.join(self._get_mad_args().upload_path, jobname)) and \
                self._adb_connect.push_file(devicemapping.device_settings.adbname, origin,
                                            os.path.join(self._get_mad_args().upload_path, jobname)) and \
                self._adb_connect.send_shell_command(
                    devicemapping.device_settings.adbname, origin,
                    "pm install -r /sdcard/Download/" + str(jobname)):
            await self._add_notice_message('File installed successfully')
        elif await self._get_device_updater().add_job(origin, jobname, job_type):
            await self._add_notice_message('Job successfully queued --> See Job Status')
        else:
            await self._add_notice_message('Job could not be set up')

        await self._redirect(self._url_for('uploaded_files'))

        # return redirect(url_for('uploaded_files', origin=str(origin), adb=useadb), code=302)
