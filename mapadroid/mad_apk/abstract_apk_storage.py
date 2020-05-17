from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional, NoReturn
from .apk_enums import APK_Arch, APK_Type


class AbstractAPKStorage(ABC):
    @abstractmethod
    def delete_file(self, package: APK_Type, architecture: APK_Arch) -> bool:
        pass

    @abstractmethod
    def get_current_version(self, package: APK_Type, architecture: APK_Arch) -> Optional[str]:
        pass

    @abstractmethod
    def get_current_package_info(self, package: APK_Type) -> Optional[dict]:
        pass

    @abstractmethod
    def get_storage_type(self) -> str:
        pass

    @abstractmethod
    def save_file(self, package: APK_Type, architecture: APK_Arch, version: str, mimetype: str, data: BytesIO,
                  retry: bool = False) -> bool:
        pass

    @abstractmethod
    def shutdown(self) -> NoReturn:
        pass
