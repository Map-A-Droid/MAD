from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.helper.SettingsWalkerToWalkerareaHelper import SettingsWalkerToWalkerareaHelper
from mapadroid.db.model import SettingsWalkerarea, SettingsWalkerToWalkerarea


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
    async def get_all_mapped_by_walker(session: AsyncSession, instance_id: int) -> Dict[int, List[SettingsWalkerarea]]:
        """

        Args:
            session:
            instance_id:

        Returns: Dict mapping walker_id to list of walkerarea instances

        """
        all_walkerareas: Dict[int, SettingsWalkerarea] = await SettingsWalkerareaHelper.get_all_mapped(session, instance_id)
        walker_area_mappings_by_walker: Dict[int, List[SettingsWalkerToWalkerarea]] = await SettingsWalkerToWalkerareaHelper.get_all_mapped(session, instance_id)
        mapped: Dict[int, List[SettingsWalkerarea]] = {}
        for walker_id, walker_to_walkerarea_mappings in walker_area_mappings_by_walker.items():
            if walker_id not in mapped:
                mapped[walker_id] = []
            walker_to_walkerarea_mappings.sort(key=lambda x: x.area_order)
            for mapping in walker_to_walkerarea_mappings:
                mapped[walker_id].append(all_walkerareas.get(mapping.walkerarea_id))
        return mapped

    @staticmethod
    async def get(session: AsyncSession, instance_id: int, walkerarea_id: int) -> Optional[SettingsWalkerarea]:
        stmt = select(SettingsWalkerarea).where(and_(SettingsWalkerarea.instance_id == instance_id,
                                                     SettingsWalkerarea.walkerarea_id == walkerarea_id))
        result = await session.execute(stmt)
        return result.scalars().first()
