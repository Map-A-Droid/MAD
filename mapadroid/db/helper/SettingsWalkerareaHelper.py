from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsWalkerarea


class SettingsWalkerareaHelper:
    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsWalkerarea]:
        stmt = select(SettingsWalkerarea).where(SettingsWalkerarea.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsWalkerarea]:
        """

        Args:
            session:
            instance_id:

        Returns: Dict mapping walkerarea_id to walkerarea instance

        """
        all_walkerareas: List[SettingsWalkerarea] = await SettingsWalkerareaHelper.get_all(session, instance_id)
        mapped: Dict[int, SettingsWalkerarea] = {}
        for walkerarea in all_walkerareas:
            mapped[walkerarea.walkerarea_id] = walkerarea
        return mapped

    @staticmethod
    def get(session: AsyncSession, instance_id: int, walkerarea_id: int) -> Optional[SettingsWalkerarea]:
        stmt = select(SettingsWalkerarea).where(and_(SettingsWalkerarea.instance_id == instance_id,
                                                     SettingsWalkerarea.walkerarea_id == walkerarea_id))
        result = await session.execute(stmt)
        return result.scalars().first()
