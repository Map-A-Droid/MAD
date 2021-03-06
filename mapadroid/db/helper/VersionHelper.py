from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Version


class VersionHelper:
    @staticmethod
    async def get_mad_version(session: AsyncSession) -> Optional[Version]:
        stmt = select(Version).where(Version.key == "mad_version")
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def update_mad_version(session: AsyncSession, version_to_set: int) -> None:
        version: Optional[Version] = await VersionHelper.get_mad_version(session)
        if not version:
            version.key = "mad_version"
        version.val = version_to_set
        session.add(version)

