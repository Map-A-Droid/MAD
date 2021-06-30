from typing import Optional, Dict

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsRoutecalc
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class SettingsRoutecalcHelper:
    @staticmethod
    async def update_instance_id(session: AsyncSession, routecalc_id: int, instance_id: int) -> None:
        stmt = update(SettingsRoutecalc).where(SettingsRoutecalc.routecalc_id == routecalc_id) \
            .values(instance_id=instance_id)
        await session.execute(stmt)

    @staticmethod
    async def reset_recalc_status(session: AsyncSession, instance_id: int) -> None:
        # This function should handle any on-boot clearing.  It is not initiated by __init__ on the off-chance that
        # a third-party integration has triggered the data_manager
        # Clear any route calcs because that thread is not active
        stmt = update(SettingsRoutecalc).where(SettingsRoutecalc.instance_id == instance_id) \
            .values(recalc_status=0)
        await session.execute(stmt)

    @staticmethod
    async def get(session: AsyncSession, routecalc_id: int) -> Optional[SettingsRoutecalc]:
        stmt = select(SettingsRoutecalc).where(SettingsRoutecalc.routecalc_id == routecalc_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsRoutecalc]:
        stmt = select(SettingsRoutecalc).where(SettingsRoutecalc.instance_id == instance_id)
        result = await session.execute(stmt)
        routecalcs: Dict[int, SettingsRoutecalc] = {}
        for routecalc in result.scalars():
            routecalcs[routecalc.routecalc_id] = routecalc
        return routecalcs
