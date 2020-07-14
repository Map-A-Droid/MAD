from typing import Dict, Optional
from .apk_enums import APK_Arch, APK_Type


class MAD_Package(object):
    """ Package definition for MAD

    Args:
        package (APK_Type): Package
        architecture (APK_Arch): Architecture of the package

    Attributes:
        file_id (int): ID from filestore_meta if saved to the database
        filename (str): User-Friendly filename
        mimetype (str): Mimetype of the package
        size (int): Size in bytes of the package
        version (str): Version of the package
    """

    file_id: Optional[int] = None
    filename: Optional[str] = None
    mimetype: Optional[str] = None
    size: Optional[int] = None
    version: Optional[str] = None

    def __init__(self, package: APK_Type, architecture: APK_Arch, **kwargs):
        self.architecture = architecture
        self.package = package
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def get_package(self, backend: bool = True):
        return {
            'arch_disp': self.architecture if backend else self.architecture.name,
            'file_id': self.file_id,
            'filename': self.filename,
            'mimetype': self.mimetype,
            'size': self.size,
            'usage_disp': self.package if backend else self.package.name,
            'version': self.version
        }

    def __str__(self):
        return str(self.get_package(backend=False))


class MAD_Packages(Dict[APK_Arch, MAD_Package]):
    pass


class MAD_APKS(Dict[APK_Type, MAD_Packages]):
    pass
