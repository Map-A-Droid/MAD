from typing import List, Optional, Dict

from aiohttp.abc import Request

from mapadroid.db.helper.MadApkAutosearchHelper import MadApkAutosearchHelper
from mapadroid.db.model import MadApkAutosearch
from mapadroid.mad_apk.utils import get_apk_status, lookup_arch_enum, is_newer_version, lookup_apk_enum
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.apk_enums import APKType, APKArch
from mapadroid.utils.custom_types import MADapks


class ApkUpdateStatusEndpoint(AbstractMadminRootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    async def get(self):
        update_info: Dict[str, Dict] = {}
        autosearch_data: List[MadApkAutosearch] = await MadApkAutosearchHelper.get_all(self._session)

        apk_info: MADapks = await get_apk_status(self._get_storage_obj())
        package: Optional[APKType] = None
        arch: Optional[APKArch] = None
        for autosearch_enttry in autosearch_data:
            arch: APKArch = lookup_arch_enum(autosearch_enttry.arch)
            package: APKType = lookup_apk_enum(autosearch_enttry.usage)
            composite_key: str = '%s_%s' % (autosearch_enttry.usage, autosearch_enttry.arch)
            update_info[composite_key]: Dict = {}
            if autosearch_enttry.download_status != 0:
                update_info[composite_key]['download_status'] = autosearch_enttry.download_status
            try:
                curr_info = apk_info[package][arch]
            except KeyError:
                curr_info = None
            if package == APKType.pogo:
                if not curr_info or is_newer_version(autosearch_enttry.version, curr_info.version):
                    update_info[composite_key]['update'] = 1
            else:
                if curr_info is None or curr_info.size is None or autosearch_enttry.version is None:
                    update_info[composite_key]['update'] = 1
                elif int(curr_info.size) != int(autosearch_enttry.version):
                    update_info[composite_key]['update'] = 1
            if not update_info[composite_key]:
                del update_info[composite_key]
        return await self._json_response(data=update_info)
