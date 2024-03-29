from typing import Dict, Optional

from mapadroid.db.model import MadApk
from mapadroid.utils.apk_enums import APKArch, APKType


class MADPackage(object):
    """ Package definition for MAD

    Args:
        package (APKType): Package
        architecture (APKArch): Architecture of the package

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

    def __init__(self, package: APKType, architecture: APKArch, mad_apk: Optional[MadApk] = None, **kwargs):
        self.architecture = architecture
        self.package = package
        if mad_apk:
            self.file_id = mad_apk.filestore_id
            self.filename = mad_apk.filename
            self.mimetype = mad_apk.mimetype
            self.size = mad_apk.size
            self.version = mad_apk.version
        for key, value in kwargs.items():
            # TODO: We need the MADApk instance here?
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


class MADPackages(Dict[APKArch, MADPackage]):
    pass


class MADapks(Dict[APKType, MADPackages]):
    pass
