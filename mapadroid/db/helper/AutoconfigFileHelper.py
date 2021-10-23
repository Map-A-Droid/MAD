import json
from typing import Optional, List

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import AutoconfigFile, SettingsAuth


class AutoconfigFileHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, name: str) -> Optional[AutoconfigFile]:
        stmt = select(AutoconfigFile).where(and_(AutoconfigFile.instance_id == instance_id,
                                                 AutoconfigFile.name == name))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_assigned_to_auth(session: AsyncSession, auth: SettingsAuth) -> List[AutoconfigFile]:
        stmt = select(AutoconfigFile).where(AutoconfigFile.instance_id == auth.instance_id)
        result = await session.execute(stmt)
        assigned: List[AutoconfigFile] = []
        for autoconfig_file in result.scalars().all():
            data = json.loads(autoconfig_file.data)
            if 'mad_auth' not in data or not data['mad_auth']:
                continue
            elif data['mad_auth'] != auth.auth_id:
                continue
            assigned.append(autoconfig_file)
        return assigned

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
