import os
import time
from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry
from mapadroid.utils.updater import JobType


class InstallFileEndpoint(AbstractControlEndpoint):
    """
    "/install_file"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('uploaded_files.html')
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
        if os.path.exists(os.path.join(self._get_mad_args().upload_path, jobname)):
            if useadb:
                if self._adb_connect.push_file(devicemapping.device_settings.adbname, origin,
                                               os.path.join(self._get_mad_args().upload_path, jobname)) and \
                        self._adb_connect.send_shell_command(
                            devicemapping.device_settings.adbname, origin,
                            "pm install -r /sdcard/Download/" + str(jobname)):
                    await self._add_notice_message('File installed successfully')
                else:
                    await self._add_notice_message('File could not be installed successfully :(')
            else:
                await self._get_device_updater().preadd_job(origin, jobname, int(time.time()), job_type)
                await self._add_notice_message('Job successfully queued --> See Job Status')

        elif int(job_type) != JobType.INSTALLATION.value:
            await self._get_device_updater().preadd_job(origin, jobname, int(time.time()), job_type)
            await self._add_notice_message('Job successfully queued --> See Job Status')
        await self._redirect(self._url_for('uploaded_files'))

        # return redirect(url_for('uploaded_files', origin=str(origin), adb=useadb), code=302)
