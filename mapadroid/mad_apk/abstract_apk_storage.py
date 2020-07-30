from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional, NoReturn
from .apk_enums import APKArch, APKType
from .custom_types import MADPackages


class AbstractAPKStorage(ABC):
    @abstractmethod
    def delete_file(self, package: APKType, architecture: APKArch) -> bool:
        """ Remove the package and update the configuration

        Args:
            package (APKType): Package to lookup
            architecture (APKArch): Architecture of the package to lookup
        """
        pass

    @abstractmethod
    def get_current_version(self, package: APKType, architecture: APKArch) -> Optional[str]:
        "Get the currently installed version of the package / architecture"
        pass

    @abstractmethod
    def get_current_package_info(self, package: APKType) -> Optional[MADPackages]:
        """ Get the current information for a given package.  If the package exists in the configuration but not the
            filesystem it will be removed from the configuration

        Args:
            package (APKType): Package to lookup

        Returns:
            None if no package is found.  MADPackages if the package lookup is successful
        """
        pass

    @abstractmethod
    def get_storage_type(self) -> str:
        pass

    @abstractmethod
    def save_file(self, package: APKType, architecture: APKArch, version: str, mimetype: str, data: BytesIO,
                  retry: bool = False) -> bool:
        """ Save the package to the storage interface.  Remove the old version if it existed

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
        pass

    @abstractmethod
    def shutdown(self) -> NoReturn:
        "Perform any required steps to safely shutdown the interface"
        pass
