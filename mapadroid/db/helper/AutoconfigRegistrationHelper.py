from typing import List, Optional, Tuple

from sqlalchemy import and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import AutoconfigRegistration, SettingsDevice


class AutoconfigRegistrationHelper:
    @staticmethod
    async def get_all_of_instance(session: AsyncSession, instance_id: int,
                                  session_id: Optional[int] = None) -> List[AutoconfigRegistration]:
        stmt = select(AutoconfigRegistration).where(AutoconfigRegistration.instance_id == instance_id)
        if session_id:
            stmt = stmt.where(AutoconfigRegistration.session_id == session_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_of_device(session: AsyncSession, instance_id: int,
                            device_id: int) -> Optional[AutoconfigRegistration]:
        stmt = select(AutoconfigRegistration).where(and_(AutoconfigRegistration.instance_id == instance_id,
                                                         AutoconfigRegistration.device_id == device_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_session_id(session: AsyncSession, instance_id: int, session_id: int) \
            -> Optional[AutoconfigRegistration]:
        stmt = select(AutoconfigRegistration).where(and_(AutoconfigRegistration.instance_id == instance_id,
                                                         AutoconfigRegistration.session_id == session_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def update_status(session: AsyncSession, instance_id: int, session_id: int, status: int) -> None:
        stmt = update(AutoconfigRegistration)\
            .where(and_(AutoconfigRegistration.instance_id == instance_id,
                        AutoconfigRegistration.session_id == session_id))\
            .values(status=status)
        await session.execute(stmt)

    @staticmethod
    async def update_ip(session: AsyncSession, instance_id: int, session_id: int, request_ip: str) -> None:
        stmt = update(AutoconfigRegistration)\
            .where(and_(AutoconfigRegistration.instance_id == instance_id,
                        AutoconfigRegistration.session_id == session_id))\
            .values(ip=request_ip)
        await session.execute(stmt)

    @staticmethod
    async def get_pending(session: AsyncSession, instance_id: int) \
            -> List[Tuple[AutoconfigRegistration, SettingsDevice]]:
        """

        Args:
            session:
            instance_id:

        Returns: List of tuples containing (session_id, ip, device_id, name/origin, status)

        Used to be
                sql = "SELECT ar.`session_id`, ar.`ip`, sd.`device_id`, sd.`name` AS 'origin', ar.`status`"\
              "FROM `autoconfig_registration` ar\n"\
              "LEFT JOIN `settings_device` sd ON sd.`device_id` = ar.`device_id`\n"\
              "WHERE ar.`instance_id` = %s"
        """
        stmt = select(AutoconfigRegistration, SettingsDevice)\
            .select_from(AutoconfigRegistration)\
            .join(SettingsDevice, SettingsDevice.device_id == AutoconfigRegistration.device_id)\
            .where(AutoconfigRegistration.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.all()

    @staticmethod
    async def delete(session: AsyncSession, instance_id: int, session_id: int) -> None:
        stmt = delete(AutoconfigRegistration)\
            .where(and_(AutoconfigRegistration.instance_id == instance_id,
                        AutoconfigRegistration.session_id == session_id))
        await session.execute(stmt)
