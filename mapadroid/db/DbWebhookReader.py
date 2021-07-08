from datetime import timezone
from typing import Tuple, List, Dict, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.helper.WeatherHelper import WeatherHelper
from mapadroid.db.model import Raid, Gym, GymDetail, Weather, TrsQuest, Pokestop, Pokemon, TrsSpawn
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import MonSeenTypes

logger = get_logger(LoggerEnums.database)


class DbWebhookReader:
    @staticmethod
    async def get_raids_changed_since(session: AsyncSession, utc_timestamp: int):
        logger.debug2("DbWebhookReader::get_raids_changed_since called")
        # TODO: Consider geofences?
        raids_changed: List[Tuple[Raid, GymDetail, Gym]] = await RaidHelper.get_raids_changed_since(session,
                                                                                                    utc_timestamp=utc_timestamp)

        ret = []
        for (raid, gym_detail, gym) in raids_changed:
            ret.append({
                "gym_id": raid.gym_id,
                "level": raid.level,
                "spawn": int(raid.spawn.replace(tzinfo=timezone.utc).timestamp()),
                "start": int(raid.start.replace(tzinfo=timezone.utc).timestamp()),
                "end": int(raid.end.replace(tzinfo=timezone.utc).timestamp()),
                "pokemon_id": raid.pokemon_id,
                "cp": raid.cp,
                "move_1": raid.move_1,
                "move_2": raid.move_2,
                "last_scanned": int(raid.last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "form": raid.form,
                "name": gym_detail.name,
                "url": gym_detail.url,
                "latitude": gym.latitude,
                "longitude": gym.longitude,
                "team_id": gym.team_id,
                "weather_boosted_condition": gym.weather_boosted_condition,
                "is_exclusive": raid.is_exclusive,
                "gender": raid.gender,
                "is_ex_raid_eligible": gym.is_ex_raid_eligible,
                "costume": raid.costume,
                "evolution": raid.evolution
            })
        return ret

    @staticmethod
    async def get_weather_changed_since(session: AsyncSession, utc_timestamp: int):
        logger.debug2("DbWebhookReader::get_weather_changed_since called")
        weather_changed: List[Weather] = await WeatherHelper.get_changed_since(session, utc_timestamp=utc_timestamp)

        ret = []
        for weather in weather_changed:
            ret.append({
                "s2_cell_id": weather.s2_cell_id,
                "latitude": weather.latitude,
                "longitude": weather.longitude,
                "cloud_level": weather.cloud_level,
                "rain_level": weather.rain_level,
                "wind_level": weather.wind_level,
                "snow_level": weather.snow_level,
                "fog_level": weather.fog_level,
                "wind_direction": weather.wind_direction,
                "gameplay_weather": weather.gameplay_weather,
                "severity": weather.severity,
                "warn_weather": weather.warn_weather,
                "world_time": weather.world_time,
                "last_updated": int(weather.last_updated.replace(tzinfo=timezone.utc).timestamp())
            })
        return ret

    @staticmethod
    async def get_quests_changed_since(session: AsyncSession, utc_timestamp: int):
        logger.debug2("DbWebhookReader::get_quests_changed_since called")
        quests_with_changes: Dict[int, Tuple[Pokestop, TrsQuest]] = await PokestopHelper.get_with_quests(session,
                                                                                                         timestamp=utc_timestamp)
        questinfo = {}
        for stop, quest in quests_with_changes.values():
            mon = "%03d" % quest.quest_pokemon_id
            form_id = "%02d" % quest.quest_pokemon_form_id
            costume_id = "%02d" % quest.quest_pokemon_costume_id
            questinfo[stop.pokestop_id] = ({
                'pokestop_id': stop.pokestop_id, 'latitude': stop.latitude, 'longitude': stop.longitude,
                'quest_type': quest.quest_type, 'quest_stardust': quest.quest_stardust,
                'quest_pokemon_id': mon, 'quest_pokemon_form_id': form_id,
                'quest_pokemon_costume_id': costume_id,
                'quest_reward_type': quest.quest_reward_type, 'quest_item_id': quest.quest_item_id,
                'quest_item_amount': quest.quest_item_amount, 'name': stop.name, 'image': stop.image,
                'quest_target': quest.quest_target,
                'quest_condition': quest.quest_condition, 'quest_timestamp': quest.quest_timestamp,
                'task': quest.quest_task, 'quest_reward': quest.quest_reward, 'quest_template': quest.quest_template,
                'is_ar_scan_eligible': stop.is_ar_scan_eligible
            })
        return questinfo

    @staticmethod
    async def get_gyms_changed_since(session: AsyncSession, utc_timestamp: int):
        logger.debug2("DbWebhookReader::get_gyms_changed_since called")
        gyms_changed: List[Tuple[Gym, GymDetail]] = await GymHelper.get_changed_since(session, utc_timestamp)

        ret = []
        for (gym, gym_detail) in gyms_changed:
            ret.append({
                "gym_id": gym.gym_id,
                "team_id": gym.team_id,
                "guard_pokemon_id": gym.guard_pokemon_id,
                "slots_available": gym.slots_available,
                "latitude": gym.latitude,
                "longitude": gym.longitude,
                "total_cp": gym.total_cp,
                "is_in_battle": gym.is_in_battle,
                "weather_boosted_condition": gym.weather_boosted_condition,
                "last_scanned": int(gym.last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "last_modified": int(gym.last_modified.replace(tzinfo=timezone.utc).timestamp()),
                "name": gym_detail.name,
                "url": gym_detail.url,
                "description": gym_detail.description,
                "is_ex_raid_eligible": gym.is_ex_raid_eligible,
                "is_ar_scan_eligible": gym.is_ar_scan_eligible
            })
        return ret

    @staticmethod
    async def get_stops_changed_since(session: AsyncSession, utc_timestamp: int):
        logger.debug2("DbWebhookReader::get_stops_changed_since called")
        stops_with_changes: List[Pokestop] = await PokestopHelper.get_changed_since_or_incident(session, utc_timestamp)
        ret = []
        for stop in stops_with_changes:
            ret.append({
                'pokestop_id': stop.pokestop_id,
                'latitude': stop.latitude,
                'longitude': stop.longitude,
                'lure_expiration': int(stop.lure_expiration.replace(
                    tzinfo=timezone.utc).timestamp()) if stop.lure_expiration is not None else None,
                'name': stop.name,
                'image': stop.image,
                'active_fort_modifier': stop.active_fort_modifier,
                "last_modified": int(stop.last_modified.replace(
                    tzinfo=timezone.utc).timestamp()) if stop.last_modified is not None else None,
                "last_updated": int(stop.last_updated.replace(
                    tzinfo=timezone.utc).timestamp()) if stop.last_updated is not None else None,
                "incident_start": int(stop.incident_start.replace(
                    tzinfo=timezone.utc).timestamp()) if stop.incident_start is not None else None,
                "incident_expiration": int(stop.incident_expiration.replace(
                    tzinfo=timezone.utc).timestamp()) if stop.incident_expiration is not None else None,
                "incident_grunt_type": stop.incident_grunt_type
            })
        return ret

    @staticmethod
    async def get_mon_changed_since(session: AsyncSession, utc_timestamp: int,
                                    mon_types: Optional[Set[MonSeenTypes]] = None):
        logger.debug2("DbWebhookReader::get_mon_changed_since called")
        mons_with_changes: List[Tuple[Pokemon, TrsSpawn, Pokestop]] = await PokemonHelper.get_changed_since(session,
                                                                                                  utc_timestamp,
                                                                                                  mon_types)

        ret = []
        for (mon, spawn) in mons_with_changes:
            if mon.latitude == 0 and mon.seen_type == MonSeenTypes.LURE_ENCOUNTER.value:
                continue
            ret.append({
                "encounter_id": mon.encounter_id,
                "pokemon_id": mon.pokemon_id,
                "last_modified": mon.last_modified,
                "spawnpoint_id": mon.spawnpoint_id,
                "latitude": mon.latitude,
                "longitude": mon.longitude,
                "disappear_time": int(mon.disappear_time.replace(tzinfo=timezone.utc).timestamp()),
                "individual_attack": mon.individual_attack,
                "individual_defense": mon.individual_defense,
                "individual_stamina": mon.individual_stamina,
                "move_1": mon.move_1,
                "move_2": mon.move_2,
                "cp": mon.cp,
                "cp_multiplier": mon.cp_multiplier,
                "gender": mon.gender,
                "form": mon.form,
                "costume": mon.costume,
                "height": mon.height,
                "weight": mon.weight,
                "weather_boosted_condition": mon.weather_boosted_condition,
                "base_catch": mon.catch_prob_1,
                "great_catch": mon.catch_prob_2,
                "ultra_catch": mon.catch_prob_3,
                "spawn_verified": True if spawn.calc_endminsec else False
            })
        return ret
