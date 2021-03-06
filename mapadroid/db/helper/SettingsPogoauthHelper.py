from sqlalchemy.future import select
from typing import Optional, List

from sqlalchemy import update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from enum import Enum

from mapadroid.db.model import SettingsRoutecalc, SettingsPogoauth
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)

class LoginType(Enum):
    GOOGLE = "google"
    PTC = "ptc"


# noinspection PyComparisonWithNone
class SettingsPogoauthHelper:
    @staticmethod
    async def get_unassigned(session: AsyncSession, instance_id: int, auth_type: Optional[LoginType]) \
            -> List[SettingsPogoauth]:
        stmt = select(SettingsPogoauth).where(and_(SettingsPogoauth.device_id == None,
                                                   SettingsPogoauth.instance_id == instance_id))
        if auth_type is not None:
            stmt = stmt.where(SettingsPogoauth.login_type == auth_type.value)
        result = await session.execute(stmt)
        return result.scalars().all()
