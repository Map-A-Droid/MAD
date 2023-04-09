from typing import Dict, List

from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.updater.JobType import JobType
from mapadroid.updater.SubJob import SubJob


class GetUploadedFilesEndpoint(AbstractControlEndpoint):
    """
    "/get_uploaded_files"
    """

    async def get(self) -> web.Response:
        # TODO: Async exec?
        available_sub_jobs: Dict[str, List[SubJob]] = self._get_device_updater().get_available_jobs()
        executable_jobs_serialized: List[Dict] = []
        for job_name, list_of_sub_jobs in available_sub_jobs.items():
            if not list_of_sub_jobs:
                continue
            elif len(list_of_sub_jobs) > 1:
                executable_jobs_serialized.append({'jobname': job_name, 'creation': '',
                                                   'type': JobType.CHAIN.value})
            else:
                type_of_job: JobType = list_of_sub_jobs[0].TYPE
                executable_jobs_serialized.append({'jobname': job_name,
                                                   'creation': '' if type_of_job != JobType.INSTALLATION
                                                   else list_of_sub_jobs[0].FIELDNAME,
                                                   'type': type_of_job.value})
        return await self._json_response(executable_jobs_serialized)
