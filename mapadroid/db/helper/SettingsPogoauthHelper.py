from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.model import (SettingsDevice, SettingsPogoauth)
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

    @staticmethod
    async def get_assigned_to_device(session: AsyncSession, instance_id: int,
                                     device_id: int) -> List[SettingsPogoauth]:
        stmt = select(SettingsPogoauth).where(and_(SettingsPogoauth.instance_id == instance_id,
                                                   SettingsPogoauth.device_id == device_id))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, instance_id: int, identifier: int) -> Optional[SettingsPogoauth]:
        stmt = select(SettingsPogoauth).where(and_(SettingsPogoauth.instance_id == instance_id,
                                                   SettingsPogoauth.account_id == identifier))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsPogoauth]:
        stmt = select(SettingsPogoauth).where(SettingsPogoauth.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsPogoauth]:
        listed: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_all(session, instance_id)
        mapped: Dict[int, SettingsPogoauth] = {}
        for auth in listed:
            mapped[auth.account_id] = auth
        return mapped

    @staticmethod
    async def get_of_autoconfig(session: AsyncSession, instance_id: int, device_id: int) -> List[SettingsPogoauth]:
        # LEFT JOIN...
        stmt = select(SettingsPogoauth) \
            .select_from(SettingsPogoauth) \
            .join(SettingsDevice, SettingsDevice.device_id == SettingsPogoauth.device_id, isouter=True) \
            .where(and_(SettingsPogoauth.instance_id == instance_id,
                        or_(SettingsDevice.device_id == None,
                            SettingsDevice.device_id == device_id)))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_available_devices(session: AsyncSession, instance_id: int, auth_id: Optional[int] = None) \
            -> Dict[int, SettingsDevice]:
        invalid_devices = set()
        avail_devices: Dict[int, SettingsDevice] = {}
        device_id: Optional[int] = None
        pogoauths: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_all(session, instance_id)
        try:
            identifier = int(auth_id)
        except (ValueError, TypeError):
            pass
        else:
            for auth in pogoauths:
                if auth.account_id == identifier:
                    device_id = auth.device_id
                    break
            if not device_id:
                # Auth isn't found. Either it doesnt exist or auth_type mismatch
                return avail_devices
        for pauth in pogoauths:
            if pauth.device_id is not None and device_id is not None and pauth.device_id != device_id:
                invalid_devices.add(pauth.device_id)
        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(session, instance_id)
        for device in devices:
            if device.device_id in invalid_devices:
                continue
            avail_devices[device.device_id] = device
        return avail_devices

    @staticmethod
    async def get_avail_accounts(session: AsyncSession, instance_id: int, auth_type: Optional[LoginType],
                                 device_id: Optional[int] = None) -> Dict[int, SettingsPogoauth]:
        accounts: Dict[int, SettingsPogoauth] = {}
        stmt = select(SettingsPogoauth).where(SettingsPogoauth.instance_id == instance_id)
        if auth_type is not None:
            stmt = stmt.where(SettingsPogoauth.login_type == auth_type.value)
        result = await session.execute(stmt)

        try:
            identifier = int(device_id)
        except (ValueError, TypeError):
            identifier = None
        # Find all unassigned accounts
        for pogoauth in result.scalars():
            if pogoauth.device_id is not None and identifier is not None and pogoauth.device_id != identifier:
                continue
            accounts[pogoauth.account_id] = pogoauth
        return accounts
