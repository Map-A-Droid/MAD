from typing import Optional, List

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import MadApkAutosearch
from mapadroid.mad_apk.apk_enums import APKType, APKArch


class MadApkAutosearchHelper:
    @staticmethod
    async def get_all(session: AsyncSession) -> List[MadApkAutosearch]:
        stmt = select(MadApkAutosearch)
        res = await session.execute(stmt)
        return res.scalar().all()

    @staticmethod
    async def delete(session: AsyncSession, package: APKType, architecture: Optional[APKArch] = None) -> None:
        stmt = delete(MadApkAutosearch).where(MadApkAutosearch.usage == package.value)
        if architecture is not None:
            stmt.where(MadApkAutosearch.arch == architecture.value)
        await session.execute(stmt)
