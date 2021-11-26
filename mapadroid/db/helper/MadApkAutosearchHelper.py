from typing import Optional, List, Dict

from sqlalchemy import and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import MadApkAutosearch
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.apk_enums import APKType, APKArch


class MadApkAutosearchHelper:
    @staticmethod
    async def get_all(session: AsyncSession) -> List[MadApkAutosearch]:
        stmt = select(MadApkAutosearch)
        res = await session.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def delete(session: AsyncSession, package: APKType, architecture: Optional[APKArch] = None) -> None:
        stmt = delete(MadApkAutosearch).where(MadApkAutosearch.usage == package.value)
        if architecture is not None:
            stmt.where(MadApkAutosearch.arch == architecture.value)
        await session.execute(stmt)

    @staticmethod
    async def insert_or_update(session: AsyncSession, package: APKType, architecture: APKArch, data: Dict) -> None:
        autosearch_entry: Optional[MadApkAutosearch] = await MadApkAutosearchHelper.get(session, package, architecture)
        if not autosearch_entry:
            autosearch_entry: MadApkAutosearch = MadApkAutosearch()
            autosearch_entry.arch = architecture.value
            autosearch_entry.usage = package.value
        # TODO: Ensure values are fetched...
        autosearch_entry.last_checked = DatetimeWrapper.now()
        for key, value in data.items():
            setattr(autosearch_entry, key, value)
        session.add(autosearch_entry)
        await session.flush([autosearch_entry])

    @staticmethod
    async def get(session: AsyncSession, package: APKType, architecture: APKArch) -> Optional[MadApkAutosearch]:
        stmt = select(MadApkAutosearch).where(and_(MadApkAutosearch.usage == package.value,
                                                   MadApkAutosearch.arch == architecture.value))
        res = await session.execute(stmt)
        return res.scalars().first()
