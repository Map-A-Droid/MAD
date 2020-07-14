from io import BytesIO
from typing import NoReturn, Optional
from .abstract_apk_storage import AbstractAPKStorage
from .custom_types import MAD_Package, MAD_Packages
from .apk_enums import APK_Arch, APK_Type
from .utils import generate_filename
from mapadroid.utils import global_variables
from threading import RLock
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.storage)


class APKStorageDatabase(AbstractAPKStorage):
    """ Storage interface for using the database.  Implements AbstractAPKStorage for ease-of-use between different
        storage mediums

    Args:
        dbc: Database wrapper

    Attributes:
        dbc: Database wrapper
        file_lock (RLock): RLock to allow updates to be thread-safe
    """
    def __init__(self, dbc):
        logger.debug('Initializing Database storage')
        self.file_lock: RLock = RLock()
        self.dbc = dbc

    def delete_file(self, package: APK_Type, architecture: APK_Arch) -> bool:
        """ Remove the package and update the configuration

        Args:
            package (APK_Type): Package to lookup
            architecture (APK_Arch): Architecture of the package to lookup
        """
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
        "Get the currently installed version of the package / architecture"
        sql: str = "SELECT `version` FROM `mad_apks` WHERE `usage` = %s AND `arch` = %s"
        return self.dbc.autofetch_value(sql, (package.value, architecture.value))

    def get_current_package_info(self, package: APK_Type) -> Optional[MAD_Packages]:
        """ Get the current information for a given package.  If the package exists in the configuration but not the
            filesystem it will be removed from the configuration

        Args:
            package (APK_Type): Package to lookup

        Returns:
            None if no package is found.  MAD_Packages if the package lookup is successful
        """
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
        """ Save the package to the database.  Remove the old version if it existed

        Args:
            package (APK_Type): Package to save
            architecture (APK_Arch): Architecture of the package to save
            version (str): Version of the package
            mimetype (str): Mimetype of the package
            data (io.BytesIO): binary contents to be saved
            retry (bool): Not used

        Returns (bool):
            Save was successful
        """
        try:
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
            chunk_size = global_variables.CHUNK_MAX_SIZE
            for chunked_data in [data.getbuffer()[i * chunk_size:(i + 1) * chunk_size] for i in
                                 range((len(data.getbuffer()) + chunk_size - 1) // chunk_size)]:
                insert_data = {
                    'filestore_id': new_id,
                    'size': len(chunked_data),
                    'data': chunked_data.tobytes()
                }
                self.dbc.autoexec_insert('filestore_chunks', insert_data)
            logger.info('Finished upload of APK')
            return True
        except:  # noqa: E722
            logger.opt(exception=True).critical('Unable to upload APK')
        return False

    def shutdown(self) -> NoReturn:
        pass
