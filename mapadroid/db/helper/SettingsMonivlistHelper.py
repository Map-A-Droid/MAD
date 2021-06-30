from typing import Dict, List, Optional

from sqlalchemy import and_, delete
from sqlalchemy.ext.asyncio import AsyncSession, AsyncResult
from sqlalchemy.future import select

from mapadroid.db.model import SettingsMonivlist, SettingsMonivlistToMon


class SettingsMonivlistHelper:
    @staticmethod
    async def get_mapped_lists(session: AsyncSession, instance_id: int) -> Dict[int, List[int]]:
        """

        Args:
            session:
            instance_id:

        Returns: Dict with keys of monlist_id and values being the raw lists of int (mon IDs)

        """
        stmt = select(SettingsMonivlist).where(SettingsMonivlist.instance_id == instance_id)
        result: AsyncResult = await session.execute(stmt)
        mapped: Dict[int, List[int]] = {}
        for mon_iv_list in result.scalars():
            mapped[mon_iv_list.monlist_id] = await SettingsMonivlistHelper.get_list(session, instance_id,
                                                                                    mon_iv_list.monlist_id)
        return mapped

    @staticmethod
    async def get_list(session: AsyncSession, instance_id: int, monlist_id: int) -> Optional[List[int]]:
        """

        Args:
            session:
            instance_id:
            monlist_id:

        Returns: the raw list of mon IDs mapped to the monlist identified by the ID passed. If there is no list present
        with that ID, None is returned.

        """
        mon_iv_list: Optional[SettingsMonivlist] = await SettingsMonivlistHelper.get_entry(session, instance_id,
                                                                                           monlist_id)
        if not mon_iv_list:
            return None
        stmt = select(SettingsMonivlistToMon) \
            .where(SettingsMonivlistToMon.monlist_id == mon_iv_list.monlist_id) \
            .order_by(SettingsMonivlistToMon.mon_order)
        mon_ids = await session.execute(stmt)
        mon_ids_raw: List[int] = []
        for mon_id_entry in mon_ids.scalars():
            mon_ids_raw.append(mon_id_entry.mon_id)
        return mon_ids_raw

    @staticmethod
    async def get_entry(session: AsyncSession, instance_id: int, monlist_id: int) -> Optional[SettingsMonivlist]:
        stmt = select(SettingsMonivlist).where(and_(SettingsMonivlist.instance_id == instance_id,
                                                    SettingsMonivlist.monlist_id == monlist_id))
        mon_iv_list_result = await session.execute(stmt)
        return mon_iv_list_result.scalars().first()

    @staticmethod
    async def get_entries_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsMonivlist]:
        stmt = select(SettingsMonivlist).where(SettingsMonivlist.instance_id == instance_id)
        result = await session.execute(stmt)
        mapped: Dict[int, SettingsMonivlist] = {}
        for mon_iv_list in result.scalars():
            mapped[mon_iv_list.monlist_id] = mon_iv_list
        return mapped

    @staticmethod
    async def delete_mapped_ids(session: AsyncSession, monlist_id: int) -> None:
        del_stmt = delete(SettingsMonivlistToMon) \
            .where(SettingsMonivlistToMon.monlist_id == monlist_id)
        await session.execute(del_stmt)

    @staticmethod
    async def set_mon_ids(session: AsyncSession, monlist_id: int, ids: List[int]) -> None:
        await SettingsMonivlistHelper.delete_mapped_ids(session, monlist_id)
        for ind, mon_id in enumerate(ids):
            entry = SettingsMonivlistToMon()
            entry.monlist_id = monlist_id
            entry.mon_id = mon_id
            entry.mon_order = ind
            session.add(entry)
