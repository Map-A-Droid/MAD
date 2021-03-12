from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
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
        result = await session.execute(stmt)
        mapped: Dict[int, List[int]] = {}
        for mon_iv_list in result:
            stmt = select(SettingsMonivlistToMon)\
                .where(SettingsMonivlistToMon.monlist_id == mon_iv_list.monlist_id)\
                .order_by(SettingsMonivlistToMon.mon_order)
            mon_ids = await session.execute(stmt)
            mon_ids_raw: List[int] = []
            for mon_id_entry in mon_ids:
                mon_ids_raw.append(mon_id_entry.mon_id)
            mapped[mon_iv_list.monlist_id] = mon_ids_raw
        return mapped
