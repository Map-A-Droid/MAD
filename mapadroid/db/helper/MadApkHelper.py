from typing import Optional

from sqlalchemy import and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import MadApk, FilestoreMeta
from mapadroid.utils.apk_enums import APKType, APKArch
from mapadroid.utils.custom_types import MADPackage, MADPackages


class MadApkHelper:
    @staticmethod
    async def get_current_version(session: AsyncSession, package: APKType, architecture: APKArch) -> Optional[str]:
        """
        Get the currently available version of the package / architecture
        Args:
            session:
            package:
            architecture:

        Returns:

        """
        apk: Optional[MadApk] = await MadApkHelper.get(session, package, architecture)
        return apk.version if apk is not None else None

    @staticmethod
    async def get_filestore_id(session: AsyncSession, package: APKType, architecture: APKArch) -> Optional[int]:
        """
        Get the filestore ID of the package / architecture
        Args:
            session:
            package:
            architecture:

        Returns:

        """
        apk: Optional[MadApk] = await MadApkHelper.get(session, package, architecture)
        return apk.filestore_id if apk is not None else None

    @staticmethod
    async def get(session: AsyncSession, package: APKType, architecture: APKArch) -> Optional[MadApk]:
        stmt = select(MadApk).where(and_(MadApk.usage == package.value,
                                         MadApk.arch == architecture.value))
        result = await session.execute(stmt)
        apk: Optional[MadApk] = result.scalars().first()
        return apk

    @staticmethod
    async def get_current_package_info(session: AsyncSession, package: APKType) -> Optional[MADPackages]:
        data = MADPackages()
        stmt = select(MadApk) \
            .where(MadApk.usage == package.value)
        result = await session.execute(stmt)
        for apk in result.scalars():
            arch = apk.arch
            row = {'arch_disp': APKArch(arch).name, 'usage_disp': APKType(package).name}
            data[APKArch(arch)] = MADPackage(APKType(package), APKArch(arch), apk, **row)
        return data if data else None

    @staticmethod
    async def delete_file(session: AsyncSession, package: APKType, architecture: APKArch) -> bool:
        """
        Remove the package/filestore entry and update the configuration
        Args:
            session:
            package:
            architecture:

        Returns:
        """
        stmt = select(MadApk).where(and_(MadApk.usage == package.value,
                                         MadApk.arch == architecture.value))
        result = await session.execute(stmt)
        apk: Optional[MadApk] = result.scalars().first()
        if not apk or not apk.filestore_id:
            return False
        del_stmt = delete(FilestoreMeta).where(FilestoreMeta.filestore_id == apk.filestore_id)
        await session.execute(del_stmt)
        await session.commit()
        return True

    @staticmethod
    async def insert(session: AsyncSession,
                               usage: APKType, arch: APKArch, version: str,
                               filename: str, file_length: int, mimetype: str) -> MadApk:
        async with session.begin_nested() as nested_transaction:
            mad_apk: MadApk = MadApk()
            # First try to fetch an existing filestore entry
            mad_apk.filename = filename
            mad_apk.size = file_length
            mad_apk.mimetype = mimetype
            mad_apk.usage = usage.value
            mad_apk.arch = arch.value
            mad_apk.version = version
            session.add(mad_apk)
            await session.flush([mad_apk])
            await nested_transaction.commit()
        return mad_apk
