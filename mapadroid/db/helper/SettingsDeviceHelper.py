from typing import Dict, List, Optional

from sqlalchemy import and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsDevice, AutoconfigRegistration, SettingsWalker, SettingsDevicepool
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class SettingsDeviceHelper:
    @staticmethod
    async def save_last_walker_position(session: AsyncSession, instance_id: int, origin: str,
                                        location: Location) -> None:
        stmt = update(SettingsDevice).where(and_(SettingsDevice.instance_id == instance_id,
                                                 SettingsDevice.name == origin))\
            .values(startcoords_of_walker=f"{location.lat}, {location.lng}")
        await session.execute(stmt)

    @staticmethod
    async def get_duplicate_mac_entries(session: AsyncSession) -> Dict[str, List[SettingsDevice]]:
        """
        Used to be called in MADmin-constructor...
        Returns: Dictionary with MAC-addresses as keys and all devices that have that MAC assigned. There are only
        entries inserted IF there is more than one device for the given MAC...
        """
        # TODO: This won't work, we need to adjust it.. (group_by, see PokemonHelper::get_all_shiny
        stmt = select(SettingsDevice.mac_address, SettingsDevice) \
            .select_from(SettingsDevice) \
            .group_by(SettingsDevice.mac_address) \
            .having(and_(func.count("*") > 1,
                         SettingsDevice.mac_address != None))
        result = await session.execute(stmt)
        duplicates: Dict[str, List[SettingsDevice]] = {}
        for mac_address, device in result.all():
            logger.warning("Duplicate MAC `{}` detected on devices {}", mac_address, device.name)
            if mac_address not in duplicates:
                duplicates[mac_address] = []
            duplicates[mac_address].append(device)
        return duplicates

    @staticmethod
    async def get(session: AsyncSession, instance_id: int, device_id: int) -> Optional[SettingsDevice]:
        stmt = select(SettingsDevice).where(and_(SettingsDevice.instance_id == instance_id,
                                                 SettingsDevice.device_id == device_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_origin(session: AsyncSession, instance_id: int, origin: str) -> Optional[SettingsDevice]:
        stmt = select(SettingsDevice).where(and_(SettingsDevice.instance_id == instance_id,
                                                 SettingsDevice.name == origin))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsDevice]:
        stmt = select(SettingsDevice).where(SettingsDevice.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_assigned_to_walker(session: AsyncSession, walker: SettingsWalker) -> List[SettingsDevice]:
        stmt = select(SettingsDevice).where(SettingsDevice.walker_id == walker.walker_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsDevice]:
        listed: List[SettingsDevice] = await SettingsDeviceHelper.get_all(session, instance_id)
        mapped: Dict[int, SettingsDevice] = {}
        for device in listed:
            mapped[device.device_id] = device
        return mapped

    @staticmethod
    async def get_device_settings_with_autoconfig_registration_pending(session: AsyncSession, instance_id: int,
                                                                       session_id: int) -> Optional[SettingsDevice]:
        stmt = select(SettingsDevice) \
            .select_from(SettingsDevice) \
            .join(AutoconfigRegistration, AutoconfigRegistration.device_id == SettingsDevice.device_id) \
            .where(and_(AutoconfigRegistration.instance_id == instance_id,
                        AutoconfigRegistration.session_id == session_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_assigned_to_pool(session: AsyncSession, pool: SettingsDevicepool) -> List[SettingsDevice]:
        stmt = select(SettingsDevice).where(SettingsDevice.pool_id == pool.pool_id)
        result = await session.execute(stmt)
        return result.scalars().all()
