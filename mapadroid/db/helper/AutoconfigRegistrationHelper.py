from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import AutoconfigRegistration


class AutoconfigRegistrationHelper:
    @staticmethod
    async def get_all_of_instance(session: AsyncSession, instance_id: int,
                                  session_id: Optional[int] = None) -> List[AutoconfigRegistration]:
        stmt = select(AutoconfigRegistration).where(AutoconfigRegistration.instance_id == instance_id)
        if session_id:
            stmt = stmt.where(AutoconfigRegistration.session_id == session_id)
        result = await session.execute(stmt)
        return result.scalars().all()
