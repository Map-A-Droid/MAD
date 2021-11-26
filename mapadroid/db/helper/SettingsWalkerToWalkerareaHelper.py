from typing import Dict, List, Optional

from sqlalchemy import and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsWalker, SettingsWalkerToWalkerarea, SettingsWalkerarea


class SettingsWalkerToWalkerareaHelper:
    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsWalkerToWalkerarea]:
        stmt = select(SettingsWalkerToWalkerarea) \
            .select_from(SettingsWalkerToWalkerarea) \
            .join(SettingsWalker, and_(SettingsWalkerToWalkerarea.walker_id == SettingsWalker.walker_id,
                                       SettingsWalker.instance_id == instance_id), isouter=True) \
            .order_by(SettingsWalkerToWalkerarea.area_order)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_of_walkerarea(session: AsyncSession, walkerarea: SettingsWalkerarea) -> List[
        SettingsWalkerToWalkerarea]:
        stmt = select(SettingsWalkerToWalkerarea).where(
            SettingsWalkerToWalkerarea.walkerarea_id == walkerarea.walkerarea_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, List[SettingsWalkerToWalkerarea]]:
        """
        Args:
            session:
            instance_id:

        Returns: Dict mapping walker_id to list of walker to area mappings

        """
        all_walkerarea_mappings: List[SettingsWalkerToWalkerarea] = await SettingsWalkerToWalkerareaHelper.get_all(
            session, instance_id)
        mapped: Dict[int, List[SettingsWalkerToWalkerarea]] = {}
        for walkerarea_mapping in all_walkerarea_mappings:
            if walkerarea_mapping.walker_id not in mapped:
                mapped[walkerarea_mapping.walker_id] = []
            mapped[walkerarea_mapping.walker_id].append(walkerarea_mapping)
        return mapped

    @staticmethod
    async def get(session: AsyncSession, instance_id: int,
                  walker_id: int) -> Optional[List[SettingsWalkerToWalkerarea]]:
        stmt = select(SettingsWalkerToWalkerarea) \
            .select_from(SettingsWalkerToWalkerarea) \
            .join(SettingsWalker, and_(SettingsWalkerToWalkerarea.walker_id == SettingsWalker.walker_id,
                                       SettingsWalker.instance_id == instance_id), isouter=True) \
            .where(SettingsWalker.walker_id == walker_id) \
            .order_by(SettingsWalkerToWalkerarea.area_order)
        result = await session.execute(stmt)
        all_of_walker: List[SettingsWalkerToWalkerarea] = []
        for walker_mapping in result.scalars().all():
            all_of_walker.append(walker_mapping)
        return all_of_walker if len(all_of_walker) > 0 else None

    @staticmethod
    async def set(session: AsyncSession, settings_walker: SettingsWalker, walker_areas: List[int]) -> None:
        del_stmt = delete(SettingsWalkerToWalkerarea) \
            .where(SettingsWalkerToWalkerarea.walker_id == settings_walker.walker_id)
        await session.execute(del_stmt)
        for ind, walkerarea_id in enumerate(walker_areas):
            entry = SettingsWalkerToWalkerarea()
            entry.walker_id = settings_walker.walker_id
            entry.area_order = ind
            entry.walkerarea_id = walkerarea_id
            session.add(entry)
