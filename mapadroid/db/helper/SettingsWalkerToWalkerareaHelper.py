from typing import Dict, List

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsWalker, SettingsWalkerToWalkerarea


class SettingsWalkerToWalkerareaHelper:
    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsWalkerToWalkerarea]:
        stmt = select(SettingsWalkerToWalkerarea)\
            .select_from(SettingsWalkerToWalkerarea)\
            .join(SettingsWalker, and_(SettingsWalkerToWalkerarea.walker_id == SettingsWalker.walker_id,
                                       SettingsWalker.instance_id == instance_id), isouter=True)\
            .order_by(SettingsWalkerToWalkerarea.area_order)
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
        all_walkerarea_mappings: List[SettingsWalkerToWalkerarea] = await SettingsWalkerToWalkerareaHelper.get_all(session, instance_id)
        mapped: Dict[int, List[SettingsWalkerToWalkerarea]] = {}
        for walkerarea_mapping in all_walkerarea_mappings:
            if walkerarea_mapping.walker_id not in mapped:
                mapped[walkerarea_mapping.walker_id] = []
            mapped[walkerarea_mapping.walker_id] = walkerarea_mapping
        return mapped
