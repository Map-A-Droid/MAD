from typing import Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import AutoconfigFile


class AutoconfigFileHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, name: str) -> Optional[AutoconfigFile]:
        stmt = select(AutoconfigFile).where(and_(AutoconfigFile.instance_id == instance_id,
                                                 AutoconfigFile.name == name))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def insert_or_update(session: AsyncSession, instance_id: int,
                               name: str, data: str) -> None:
        config: AutoconfigFile = await AutoconfigFileHelper.get(session, instance_id, name)
        if not config:
            config = AutoconfigFile()
            config.instance_id = instance_id
            config.name = name
        config.data = data.encode("utf-8")
        session.add(config)
