import datetime
from typing import Dict, Optional

from loguru import logger

from mapadroid.account_handler.AbstractAccountHandler import (
    AbstractAccountHandler, AccountPurpose, BurnType)
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.model import SettingsDevice, SettingsPogoauth
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.gamemechanicutil import calculate_cooldown
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.global_variables import (MAINTENANCE_COOLDOWN_HOURS,
                                              MIN_LEVEL_IV, MIN_LEVEL_RAID,
                                              QUEST_WALK_SPEED_CALCULATED)


class AccountHandler(AbstractAccountHandler):
    _db_wrapper: DbWrapper

    def __init__(self, db_wrapper: DbWrapper):
        self._db_wrapper = db_wrapper

    async def get_account(self, device_id: int, purpose: AccountPurpose,
                          location_to_scan: Location, including_google: bool = True) -> Optional[SettingsPogoauth]:
        # First, fetch all pogoauth accounts
        async with self._db_wrapper as session, session:
            device_entry: Optional[SettingsDevice] = await SettingsDeviceHelper.get(session,
                                                                                    self._db_wrapper.get_instance_id(),
                                                                                    device_id)
            if not device_entry:
                logger.warning("Invalid device ID {} passed to fetch an account for it", device_id)
                return None
            # TODO: Filter only unassigned or assigned to same device first
            logins: Dict[int, SettingsPogoauth] = await SettingsPogoauthHelper.get_avail_accounts(
                session, self._db_wrapper.get_instance_id(), auth_type=None, device_id=device_id)
            # Filter all burnt and all which do not match the purpose. E.g., if the purpose is mon scanning,
            logins_filtered = [auth_entry for auth_id, auth_entry in logins.items() if not self._is_burnt(auth_entry)
                               and self._is_usable_for_purpose(auth_entry, purpose, location_to_scan)]
            logins_filtered.sort(key=lambda x: DatetimeWrapper.fromtimestamp(0) if x.last_burn is None else x.last_burn)
            login_to_use: Optional[SettingsPogoauth] = None
            if not logins_filtered:
                logger.warning("No auth found for {}", device_id)
                return None
            # Check if there is a google login assigned to the device which is still in the list
            # If that is the case, try to login - if there is a keyblob, that's ok. If not, we will thus renew it
            for login in logins_filtered:
                if login.login_type == LoginType.PTC.value:
                    continue
                elif login.username in device_entry.ggl_login_mail:
                    logger.info("Shortcut auth selection to google login {} set for device {}",
                                login.username, device_entry.name)
                    login_to_use = login
                    break
            else:
                # No google login was found for the device but we only have accounts which should be fine for
                # the purpose by now. Simply pop one
                login_to_use = logins_filtered.pop(0)
                # TODO: prefer keyblob accounts once keyblobs can be used (RGC support needed)
            # Remove marking of current SettingsPogoauth holding the deviceID
            currently_assigned: Optional[SettingsPogoauth] = await SettingsPogoauthHelper.get_assigned_to_device(
                session, device_id)
            if currently_assigned:
                currently_assigned.device_id = None
                session.add(currently_assigned)
            # TODO: Ensure login_to_use is not the same as currently_assigned
            # Mark login to be used with the device ID to indicate the now unavailable account
            login_to_use.device_id = device_id
            async with session.begin_nested() as nested:
                session.add(login_to_use)
                await nested.commit()
            # Expunge is needed to not automatically have attempts to refresh values outside a DB session
            session.expunge(login_to_use)
            await session.commit()
            return login_to_use
            # TODO: try/except

    async def notify_logout(self, device_id: int) -> None:
        async with self._db_wrapper as session, session:
            currently_assigned: Optional[SettingsPogoauth] = await SettingsPogoauthHelper.get_assigned_to_device(
                session, device_id)
            if currently_assigned:
                currently_assigned.device_id = None
                session.add(currently_assigned)
                await session.commit()

    async def mark_burnt(self, device_id: int, burn_type: Optional[BurnType]) -> None:
        async with self._db_wrapper as session, session:
            existing_auth: Optional[SettingsPogoauth] = await SettingsPogoauthHelper.get_assigned_to_device(
                session, device_id=device_id)
            if not existing_auth:
                # TODO: Raise?
                return
            logger.warning("Marking account {} (ID {}) assigned to {} as {}",
                           existing_auth.username, existing_auth.account_id,
                           device_id, burn_type)
            await SettingsPogoauthHelper.mark_burnt(session, instance_id=self._db_wrapper.get_instance_id(),
                                                    account_id=existing_auth.account_id,
                                                    burn_type=burn_type)

    async def set_last_softban_action(self, device_id: int, time_of_action: datetime.datetime,
                                      location_of_action: Location) -> None:
        async with self._db_wrapper as session, session:
            await SettingsPogoauthHelper.set_last_softban_action(session,
                                                                 device_id, location_of_action,
                                                                 int(time_of_action.timestamp()))
            await session.commit()

    async def set_level(self, device_id: int, level: int) -> None:
        async with self._db_wrapper as session, session:
            await SettingsPogoauthHelper.set_level(session,
                                                   device_id=device_id,
                                                   level=level)
            await session.commit()

    async def get_assigned_username(self, device_id: int) -> Optional[str]:
        async with self._db_wrapper as session, session:
            device_entry: Optional[SettingsDevice] = await SettingsDeviceHelper.get(
                session, self._db_wrapper.get_instance_id(), device_id)
            if not device_entry:
                logger.warning("Device ID {} not found in device table", device_id)
                return None
            currently_assigned: Optional[SettingsPogoauth] = await SettingsPogoauthHelper.get_assigned_to_device(
                session, device_entry.device_id)
            return None if not currently_assigned else currently_assigned.username

    def _is_burnt(self, auth: SettingsPogoauth) -> bool:
        """
        Evaluates whether a login is considered not usable based on the last known burning
        Args:
            auth:

        Returns:

        """
        if auth.last_burn_type is None:
            return False
        # Account has a burn type, evaluate the cooldown duration
        elif auth.last_burn_type == BurnType.BAN.value:
            # TODO: Differentiate different ban types?
            return True
        elif auth.last_burn_type == BurnType.MAINTENANCE.value:
            # Account had the maintenance screen, check whether the set duration of MAINTENANCE_COOLDOWN_HOURS passed
            return auth.last_burn + datetime.timedelta(hours=MAINTENANCE_COOLDOWN_HOURS) < DatetimeWrapper.now()

        return False

    def _is_usable_for_purpose(self, auth: SettingsPogoauth, purpose: AccountPurpose,
                               location_to_scan: Location) -> bool:
        if purpose == AccountPurpose.MON_RAID:
            # No IV scanning or just raids
            return auth.level >= MIN_LEVEL_RAID
        elif purpose == AccountPurpose.IV:
            # Check how many mons were encountered before as this could indicate a maintenance screen popping up
            # TODO
            return auth.level >= MIN_LEVEL_IV
        elif purpose in [AccountPurpose.LEVEL, AccountPurpose.QUEST, AccountPurpose.IV_QUEST]:
            # Depending on last softban action and distance to the location thereof
            if auth.level is not None:
                if purpose == AccountPurpose.IV_QUEST and auth.level < MIN_LEVEL_IV:
                    return False
                elif purpose == AccountPurpose.LEVEL and auth.level >= MIN_LEVEL_IV:
                    return False

            if not auth.last_softban_action_location:
                return True
            last_action_location: Location = Location(auth.last_softban_action_location[0],
                                                      auth.last_softban_action_location[1])
            distance_last_action = get_distance_of_two_points_in_meters(last_action_location.lat,
                                                                        last_action_location.lng,
                                                                        location_to_scan.lat,
                                                                        location_to_scan.lng)
            cooldown_seconds = calculate_cooldown(distance_last_action, QUEST_WALK_SPEED_CALCULATED)
            return DatetimeWrapper.now() > auth.last_softban_action + datetime.timedelta(seconds=cooldown_seconds)
