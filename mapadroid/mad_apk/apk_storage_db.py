from io import BytesIO
from typing import Dict, NoReturn, Optional
from .abstract_apk_storage import AbstractAPKStorage
from .custom_types import MAD_Package, MAD_Packages
from .apk_enums import APK_Arch, APK_Type
from .utils import generate_filename
from mapadroid.utils import global_variables
from mapadroid.utils.logging import logger
from threading import RLock


class APKStorageDatabase(AbstractAPKStorage):

    def __init__(self, dbc):
        logger.debug('Initializing Database storage')
        self.file_lock: RLock = RLock()
        self.dbc = dbc

    def delete_file(self, package: APK_Type, architecture: APK_Arch) -> bool:
        filestore_id_sql: str = "SELECT `filestore_id` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
        filestore_id: Optional[int] = self.dbc.autofetch_value(filestore_id_sql,
                                                               args=(package.value, architecture.value,))
        if filestore_id:
            delete_data = {
                'filestore_id': filestore_id
            }
            self.dbc.autoexec_delete('filestore_meta', delete_data)
            return True
        return False

    def get_current_version(self, package: APK_Type, architecture: APK_Arch) -> Optional[str]:
        sql: str = "SELECT `version` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
        return self.dbc.autofetch_value(sql, (package.value, architecture.value))

    def get_current_package_info(self, package: APK_Type) -> Optional[MAD_Packages]:
        data = MAD_Packages()
        sql = "SELECT ma.`version`, ma.`arch`, fm.`filename`, fm.`size`, fm.`mimetype`\n"\
              "FROM `mad_apks` ma\n"\
              "INNER JOIN `filestore_meta` fm ON fm.`filestore_id` = ma.`filestore_id`\n"\
              "WHERE ma.`usage` = %s"
        for row in self.dbc.autofetch_all(sql, (package.value)):
            arch = row['arch']
            row['arch_disp'] = APK_Arch(arch).name
            row['usage_disp'] = APK_Type(package).name
            data[APK_Arch(arch)] = MAD_Package(APK_Type(package), APK_Arch(arch), **row)
        if data:
            return data
        return None

    def get_storage_type(self) -> str:
        return 'db'

    def save_file(self, package: APK_Type, architecture: APK_Arch, version: str, mimetype: str, data: BytesIO,
                  retry: bool = False) -> bool:
        try:
            # Determine if we already have this file-type uploaded.  If so, remove it once the new one is
            # completed and update the id
            self.delete_file(package, architecture)
            file_length: int = data.getbuffer().nbytes
            filename: str = generate_filename(package, architecture, version, mimetype)
            insert_data = {
                'filename': filename,
                'size': file_length,
                'mimetype': mimetype,
            }
            new_id: int = self.dbc.autoexec_insert('filestore_meta', insert_data)
            insert_data = {
                'filestore_id': new_id,
                'usage': package.value,
                'arch': architecture.value,
                'version': version,
            }
            self.dbc.autoexec_insert('mad_apks', insert_data, optype='ON DUPLICATE')
            logger.info('Starting upload of APK')
            while True:
                chunked_data: bytes = data.read(global_variables.CHUNK_MAX_SIZE)
                if not chunked_data:
                    break
                insert_data = {
                    'filestore_id': new_id,
                    'size': len(chunked_data),
                    'data': chunked_data
                }
                self.dbc.autoexec_insert('filestore_chunks', insert_data)
            logger.info('Finished upload of APK')
            return True
        except:  # noqa: E722
            logger.opt(exception=True).critical('Unable to upload APK')
        return False

    def shutdown(self) -> NoReturn:
        pass
