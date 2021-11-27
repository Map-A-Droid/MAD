from io import BytesIO
from typing import Optional

from mapadroid.utils import global_variables
from mapadroid.utils.apk_enums import APKArch, APKType
from mapadroid.utils.custom_types import MADPackages
from mapadroid.utils.logging import LoggerEnums, get_logger
from .abstract_apk_storage import AbstractAPKStorage
from .utils import generate_filename
from ..db.DbWrapper import DbWrapper
from ..db.helper.FilestoreChunkHelper import FilestoreChunkHelper
from ..db.helper.FilestoreMetaHelper import FilestoreMetaHelper
from ..db.helper.MadApkHelper import MadApkHelper
from ..db.model import FilestoreMeta, MadApk

logger = get_logger(LoggerEnums.storage)


class APKStorageDatabase(AbstractAPKStorage):
    """ Storage interface for using the database.  Implements AbstractAPKStorage for ease-of-use between different
        storage mediums

    Args:
        db_wrapper: Database wrapper

    Attributes:
        db_wrapper: Database wrapper
    """

    def __init__(self, db_wrapper: DbWrapper, token: Optional[str]):
        super().__init__(token)
        logger.debug('Initializing Database storage')
        self.db_wrapper = db_wrapper

    async def setup(self):
        pass

    async def delete_file(self, package: APKType, architecture: APKArch) -> bool:
        """ Remove the package and update the configuration

        Args:
            package (APKType): Package to lookup
            architecture (APKArch): Architecture of the package to lookup
        """
        async with self.db_wrapper as session, session:
            # TODO: Maybe move session further up the call stack for proper transactions?
            try:
                result = await MadApkHelper.delete_file(session, package, architecture)
            except Exception as e:
                logger.warning("Failed deleting apk in DB: {}", e)
        return result

    async def get_current_version(self, package: APKType, architecture: APKArch) -> Optional[str]:
        "Get the currently installed version of the package / architecture"
        async with self.db_wrapper as session, session:
            # TODO: Maybe move session further up the call stack for proper transactions?
            return await MadApkHelper.get_current_version(session, package, architecture)

    async def get_current_package_info(self, package: APKType) -> Optional[MADPackages]:
        """ Get the current information for a given package.  If the package exists in the configuration but not the
            filesystem it will be removed from the configuration

        Args:
            package (APKType): Package to lookup

        Returns:
            None if no package is found.  MADPackages if the package lookup is successful
        """
        async with self.db_wrapper as session, session:
            # TODO: Maybe move session further up the call stack for proper transactions?
            return await MadApkHelper.get_current_package_info(session, package)

    def get_storage_type(self) -> str:
        return 'db'

    async def reload(self) -> None:
        pass

    async def save_file(self, package: APKType, architecture: APKArch, version: str, mimetype: str, data: BytesIO,
                        retry: bool = False) -> bool:
        """ Save the package to the database.  Remove the old version if it existed

        Args:
            package (APKType): Package to save
            architecture (APKArch): Architecture of the package to save
            version (str): Version of the package
            mimetype (str): Mimetype of the package
            data (io.BytesIO): binary contents to be saved
            retry (bool): Not used

        Returns (bool):
            Save was successful
        """
        # TODO: Async DB accesses...
        async with self.db_wrapper as session, session:
            try:
                await self.delete_file(package, architecture)
                file_length: int = data.getbuffer().nbytes
                filename: str = generate_filename(package, architecture, version, mimetype)

                mad_apk: MadApk = await MadApkHelper.insert(session, package, architecture, version,
                                                            filename,
                                                            file_length, mimetype
                                                            )
                logger.info('Starting upload of APK')
                chunk_size = global_variables.CHUNK_MAX_SIZE
                for chunked_data in [data.getbuffer()[i * chunk_size:(i + 1) * chunk_size] for i in
                                     range((len(data.getbuffer()) + chunk_size - 1) // chunk_size)]:
                    await FilestoreChunkHelper.insert(session, mad_apk.filestore_id, len(chunked_data),
                                                      chunked_data.tobytes())
                logger.info('Finished upload of APK')
                await session.commit()
                return True
            except Exception as e:  # noqa: E722 B001
                logger.warning("Unable to save/upload apk: {}", e, exc_info=True)
            return False

    async def shutdown(self) -> None:
        pass
