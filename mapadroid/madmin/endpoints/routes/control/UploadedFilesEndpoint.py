from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class UploadedFilesEndpoint(AbstractControlEndpoint):
    """
    "/uploaded_files"
    """

    @aiohttp_jinja2.template('uploaded_files.html')
    @expand_context()
    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False
        return {"responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
                "title": "Uploaded Files",
                "origin": origin, "adb": useadb}
