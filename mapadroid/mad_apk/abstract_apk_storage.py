from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional, NoReturn
from .apk_enums import APK_Arch, APK_Type
from .custom_types import MAD_Packages


class AbstractAPKStorage(ABC):
    @abstractmethod
    def delete_file(self, package: APK_Type, architecture: APK_Arch) -> bool:
        """ Remove the package and update the configuration

        Args:
            package (APK_Type): Package to lookup
            architecture (APK_Arch): Architecture of the package to lookup
        """
        pass

    @abstractmethod
    def get_current_version(self, package: APK_Type, architecture: APK_Arch) -> Optional[str]:
        "Get the currently installed version of the package / architecture"
        pass

    @abstractmethod
    def get_current_package_info(self, package: APK_Type) -> Optional[MAD_Packages]:
        """ Get the current information for a given package.  If the package exists in the configuration but not the
            filesystem it will be removed from the configuration

        Args:
            package (APK_Type): Package to lookup

        Returns:
            None if no package is found.  MAD_Packages if the package lookup is successful
        """
        pass

    @abstractmethod
    def get_storage_type(self) -> str:
        pass

    @abstractmethod
    def save_file(self, package: APK_Type, architecture: APK_Arch, version: str, mimetype: str, data: BytesIO,
                  retry: bool = False) -> bool:
        """ Save the package to the storage interface.  Remove the old version if it existed

        Args:
            package (APK_Type): Package to save
            architecture (APK_Arch): Architecture of the package to save
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
