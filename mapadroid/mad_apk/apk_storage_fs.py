import functools
import json
import os
import re
from copy import copy
from functools import wraps
from io import BytesIO
from typing import Any, ClassVar, Optional

from aiofile import async_open
from asyncio_rlock import RLock
from mapadroid.utils.json_encoder import MADEncoder
from mapadroid.utils.logging import LoggerEnums, get_logger

from .abstract_apk_storage import AbstractAPKStorage
from .apk_enums import APKArch, APKType
from .custom_types import MADapks, MADPackage, MADPackages
from .utils import generate_filename, lookup_apk_enum, lookup_arch_enum

logger = get_logger(LoggerEnums.storage)


def ensure_exists(func) -> Any:
    """
    Throws FileNotFoundError if not present...
    Args:
        func:

    Returns:

    """
    async def decorated(self, *args, **kwargs):
        await self.validate_file(args[0], args[1])
        return await func(self, *args, **kwargs)
    return decorated


def ensure_config_file(func) -> Any:
    async def wrapped(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except FileNotFoundError:
            logger.info('Configuration file not found.  Recreating')
            async with self._lock:
                self.__create_structure()
                self.__create_config()
            return await func(self, *args, **kwargs)
        except json.decoder.JSONDecodeError:
            logger.warning('Corrupted MAD APK json file.  Recreating')
            self.reload()
            return await func(self, *args, **kwargs)
    return wrapped


class APKStorageFilesystem(AbstractAPKStorage):
    """ Storage interface for using the filesystem.  Implements AbstractAPKStorage for ease-of-use between different
        storage mediums

    Args:
        application_args: Arguments used at startup

    Attributes:
        apks (MADapks): All APKs known to the storage system
        config_apk_dir (str): Root storage directory for packages
        config_filepath (str): Path to the configuration file
    """
    # TODO: Somehow get async locking running?...
    config_apks: ClassVar[str] = 'mad_apk'
    apks: MADapks
    config_apk_dir: str
    config_filepath: str

    def __init__(self, application_args):
        logger.debug('Initializing FileSystem storage')
        self.config_apk_dir: str = application_args.temp_path + '/' + APKStorageFilesystem.config_apks
        self.config_filepath: str = '{}/config.json'.format(self.config_apk_dir)
        self.apks = MADapks()
        self._lock = None

    async def setup(self):
        self._lock: RLock = RLock()
        async with self._lock:
            await self.reload()

    @ensure_config_file
    async def __create_config(self, delete_config: bool = False) -> None:
        """ Creates and saves the configuration

        Examines the contents from self.config_apk_dir and builds out the configuration based off each available file.

        Args:
            delete_config (bool): If the current configuration file should be removed and re-created
        """
        async with self._lock:
            if delete_config:
                try:
                    os.unlink(self.config_filepath)
                except FileNotFoundError:
                    pass
            if not os.path.isfile(self.config_filepath) or delete_config:
                # Attempt to rebuild the config if it was corrupted in some way
                mad_filematch = re.compile(r'(\S+)__(\S+)__(\S+)\.(.*)$')
                for filename in os.listdir(self.config_apk_dir):
                    try:
                        matched = mad_filematch.match(filename)
                        if not matched:
                            continue
                        packagename, version, architecture, apk_format = matched.groups()
                        if apk_format == 'zip':
                            mimetype = 'application/zip'
                        else:
                            mimetype = 'application/vnd.android.package-archive'
                        arch = lookup_arch_enum(architecture)
                        apk_family = lookup_apk_enum(packagename)
                        fullpath = '{}/{}'.format(self.config_apk_dir, filename)
                        package: dict = {
                            'version': version,
                            'file_id': None,
                            'filename': filename,
                            'mimetype': mimetype,
                            'size': os.stat(fullpath).st_size,
                        }
                        if apk_family not in self.apks:
                            self.apks[apk_family] = MADPackages()
                        self.apks[apk_family][arch] = MADPackage(apk_family, arch, **package)
                    except ValueError:
                        continue
                await self.save_configuration()
            else:
                updated: bool = False
                with open(self.config_filepath, 'rb') as fh:
                    conf = json.load(fh)
                    for apk_family, apks in conf.items():
                        for arch, apk_info in apks.items():
                            if not os.path.isfile(self.get_package_path(apk_info['filename'])):
                                logger.info('APK {} no longer exists.  Removing the file', apk_info.filename)
                                updated = True
                            else:
                                if apk_family not in self.apks:
                                    self.apks[apk_family] = MADPackages()
                                self.apks[apk_family][arch]: MADPackage(apk_family, arch, **apk_info)
                if updated:
                    await self.save_configuration()

    async def __create_structure(self) -> None:
        "Creates the filestructure required for saving packages and configuration"
        async with self._lock:
            if not os.path.isdir(self.config_apk_dir):
                logger.debug('Creating APK directory')
                os.mkdir(self.config_apk_dir)

    @ensure_config_file
    @ensure_exists
    async def delete_file(self, package: APKType, architecture: APKArch) -> bool:
        """ Remove the package and update the configuration

        Args:
            package (APKType): Package to lookup
            architecture (APKArch): Architecture of the package to lookup
        """
        apk_info: MADPackage = self.apks[package][architecture]
        os.unlink(self.get_package_path(apk_info.filename))
        del self.apks[package][architecture]
        await self.save_configuration()
        return True

    def get_package_path(self, filename: str):
        "Generate the packpage path based off the filename"
        return'{}/{}'.format(self.config_apk_dir, filename)

    @ensure_config_file
    @ensure_exists
    async def get_current_version(self, package: APKType, architecture: APKArch) -> Optional[str]:
        "Get the currently installed version of the package / architecture"
        apk_info: MADPackage = self.apks[package][architecture]
        version = apk_info.version
        return version

    @ensure_config_file
    async def get_current_package_info(self, package: APKType) -> Optional[MADPackages]:
        """ Get the current information for a given package.  If the package exists in the configuration but not the
            filesystem it will be removed from the configuration

        Args:
            package (APKType): Package to lookup

        Returns:
            None if no package is found.  MADPackages if the package lookup is successful
        """
        # TODO: Async handling
        async with self._lock:
            try:
                data = copy(self.apks[package])
                for arch, _apk_info in data.items():
                    await self.validate_file(package, arch)
            except KeyError:
                logger.debug('Package has not been downloaded')
            try:
                if self.apks[package]:
                    return self.apks[package]
                else:
                    return None
            except KeyError:
                logger.debug('Package has not been downloaded')
                return None

    def get_storage_type(self) -> str:
        return 'fs'

    async def reload(self) -> None:
        async with self._lock:
            await self.__create_structure()
            await self.__create_config(delete_config=True)

    async def save_configuration(self) -> None:
        """Save the current configuration to the filesystem with human-readable indentation"""
        async with self._lock:
            async with async_open(self.config_filepath, 'w+') as fh:
                # TODO: pass async read data to dump
                json_encoded: str = json.dumps(self.apks, indent=2, cls= MADEncoder)
                await fh.write(json_encoded)
                # json.dump(self.apks, fh, indent=2, cls=MADEncoder)

    @ensure_config_file
    async def shutdown(self) -> None:
        """Save the configuration prior to shutdown"""
        await self.save_configuration()

    @ensure_config_file
    async def save_file(self, package: APKType, architecture: APKArch, version: str, mimetype: str, data: BytesIO,
                        retry: bool = False) -> bool:
        """ Save the package to the filesystem.  Remove the old version if it existed

        Args:
            package (APKType): Package to save
            architecture (APKArch): Architecture of the package to save
            version (str): Version of the package
            mimetype (str): Mimetype of the package
            data (io.BytesIO): binary contents to be saved
            retry (bool): Attempt to re-save the file if an issue occurs

        Returns (bool):
            Save was successful
        """
        try:
            filename = generate_filename(package, architecture, version, mimetype)
            async with self._lock:
                try:
                    await self.delete_file(package, architecture)
                    logger.debug2('Successfully removed the previous version')
                except (FileNotFoundError, KeyError):
                    pass
                try:
                    await self.delete_file(package, architecture)
                except (TypeError, KeyError):
                    pass
                try:
                    async with async_open(self.get_package_path(filename), 'wb+') as fh:
                        await fh.write(data.getbuffer())
                except FileNotFoundError:
                    if retry:
                        await self.__create_structure()
                        return await self.save_file(package, architecture, version, mimetype, data)
                else:
                    info = {
                        'version': version,
                        'file_id': None,
                        'filename': filename,
                        'mimetype': mimetype,
                        'size': os.stat(self.get_package_path(filename)).st_size,
                    }
                    if package not in self.apks:
                        self.apks[package] = MADPackages()
                    self.apks[package][architecture] = MADPackage(package, architecture, **info)
                    await self.save_configuration()
                    logger.info('Successfully saved {} to the disk', filename)
                    return True
        except Exception:  # noqa: E722
            logger.opt(exception=True).critical('Unable to upload APK')
        return False

    async def validate_file(self, package: APKType, architecture: APKArch) -> bool:
        """ Validate that the file exists on the filesystem.  Remove from the config if it does not exist

        Args:
            package (APKType): Package to save
            architecture (APKArch): Architecture of the package to save

        Return (bool):
            Package / Architecture is value
        """
        try:
            apk_info: MADPackage = self.apks[package][architecture]
            package_path = self.get_package_path(apk_info.filename)
            if not os.path.isfile(package_path):
                del self.apks[package][architecture]
                await self.save_configuration()
                raise FileNotFoundError(package_path)
            return True
        except KeyError:
            raise FileNotFoundError
