from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import MadApkAutosearch
from mapadroid.mad_apk import APKArch, APKType


class MadApkAutosearchHelper:
    @staticmethod
    async def delete(session: AsyncSession, package: APKType, architecture: Optional[APKArch] = None) -> None:
        stmt = delete(MadApkAutosearch).where(MadApkAutosearch.usage == package.value)
        if architecture is not None:
            stmt.where(MadApkAutosearch.arch == architecture.value)
        await session.execute(stmt)
