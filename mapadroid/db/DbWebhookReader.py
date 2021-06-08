from datetime import datetime, timezone
from typing import Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.model import Raid, Gym, GymDetail
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbWebhookReader:
    @staticmethod
    async def get_raids_changed_since(session: AsyncSession, timestamp):
        logger.debug2("DbWebhookReader::get_raids_changed_since called")
        # TODO: Consider geofences?
        raids_changed: List[Tuple[Raid, GymDetail, Gym]] = await RaidHelper.get_raids_changed_since(session,
                                                                                                    utc_timestamp=timestamp)

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

    def get_weather_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_weather_changed_since called")
        query = (
            "SELECT * "
            "FROM weather "
            "WHERE last_updated >= %s"
        )
        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (s2_cell_id, latitude, longitude, cloud_level, rain_level, wind_level,
             snow_level, fog_level, wind_direction, gameplay_weather, severity,
             warn_weather, world_time, last_updated) in res:
            ret.append({
                "s2_cell_id": s2_cell_id,
                "latitude": latitude,
                "longitude": longitude,
                "cloud_level": cloud_level,
                "rain_level": rain_level,
                "wind_level": wind_level,
                "snow_level": snow_level,
                "fog_level": fog_level,
                "wind_direction": wind_direction,
                "gameplay_weather": gameplay_weather,
                "severity": severity,
                "warn_weather": warn_weather,
                "world_time": world_time,
                "last_updated": int(last_updated.replace(tzinfo=timezone.utc).timestamp())
            })
        return ret

    def get_quests_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_quests_changed_since called")
        return self._db_wrapper.quests_from_db(timestamp=timestamp)

    def get_gyms_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_gyms_changed_since called")
        query = (
            "SELECT name, description, url, gym.gym_id, team_id, guard_pokemon_id, slots_available, "
            "latitude, longitude, total_cp, is_in_battle, weather_boosted_condition, "
            "last_modified, gym.last_scanned, gym.is_ex_raid_eligible, gym.is_ar_scan_eligible "
            "FROM gym "
            "LEFT JOIN gymdetails ON gym.gym_id = gymdetails.gym_id "
            "WHERE gym.last_scanned >= %s"
        )
        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (name, description, url, gym_id, team_id, guard_pokemon_id, slots_available,
             latitude, longitude, total_cp, is_in_battle, weather_boosted_condition,
             last_modified, last_scanned, is_ex_raid_eligible, is_ar_scan_eligible) in res:
            ret.append({
                "gym_id": gym_id,
                "team_id": team_id,
                "guard_pokemon_id": guard_pokemon_id,
                "slots_available": slots_available,
                "latitude": latitude,
                "longitude": longitude,
                "total_cp": total_cp,
                "is_in_battle": is_in_battle,
                "weather_boosted_condition": weather_boosted_condition,
                "last_scanned": int(last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "last_modified": int(last_modified.replace(tzinfo=timezone.utc).timestamp()),
                "name": name,
                "url": url,
                "description": description,
                "is_ex_raid_eligible": is_ex_raid_eligible,
                "is_ar_scan_eligible": is_ar_scan_eligible
            })
        return ret

    def get_stops_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_stops_changed_since called")
        query = (
            "SELECT pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier, "
            "last_modified, last_updated, incident_start, incident_expiration, incident_grunt_type "
            "FROM pokestop "
            "WHERE last_updated >= %s AND (DATEDIFF(lure_expiration, '1970-01-01 00:00:00') > 0 OR "
            "incident_start IS NOT NULL)"
        )
        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (pokestop_id, latitude, longitude, lure_expiration, name, image, active_fort_modifier,
             last_modified, last_updated, incident_start, incident_expiration, incident_grunt_type) in res:
            ret.append({
                'pokestop_id': pokestop_id,
                'latitude': latitude,
                'longitude': longitude,
                'lure_expiration': int(lure_expiration.replace(
                    tzinfo=timezone.utc).timestamp()) if lure_expiration is not None else None,
                'name': name,
                'image': image,
                'active_fort_modifier': active_fort_modifier,
                "last_modified": int(last_modified.replace(
                    tzinfo=timezone.utc).timestamp()) if last_modified is not None else None,
                "last_updated": int(last_updated.replace(
                    tzinfo=timezone.utc).timestamp()) if last_updated is not None else None,
                "incident_start": int(incident_start.replace(
                    tzinfo=timezone.utc).timestamp()) if incident_start is not None else None,
                "incident_expiration": int(incident_expiration.replace(
                    tzinfo=timezone.utc).timestamp()) if incident_expiration is not None else None,
                "incident_grunt_type": incident_grunt_type
            })
        return ret

    def get_mon_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_mon_changed_since called")
        query = (
            "SELECT encounter_id, spawnpoint_id, pokemon_id, pokemon.latitude, pokemon.longitude, "
            "disappear_time, individual_attack, individual_defense, individual_stamina, "
            "move_1, move_2, cp, cp_multiplier, weight, height, gender, form, costume, "
            "weather_boosted_condition, last_modified, catch_prob_1, catch_prob_2, catch_prob_3, "
            "(trs_spawn.calc_endminsec IS NOT NULL) AS verified "
            "FROM pokemon "
            "INNER JOIN trs_spawn ON pokemon.spawnpoint_id = trs_spawn.spawnpoint "
            "WHERE last_modified >= %s"
        )
        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (encounter_id, spawnpoint_id, pokemon_id, latitude,
             longitude, disappear_time, individual_attack,
             individual_defense, individual_stamina, move_1, move_2,
             cp, cp_multiplier, weight, height, gender, form, costume,
             weather_boosted_condition, last_modified, catch_prob_1, catch_prob_2, catch_prob_3,
             verified) in res:
            ret.append({
                "encounter_id": encounter_id,
                "pokemon_id": pokemon_id,
                "last_modified": last_modified,
                "spawnpoint_id": spawnpoint_id,
                "latitude": latitude,
                "longitude": longitude,
                "disappear_time": int(disappear_time.replace(tzinfo=timezone.utc).timestamp()),
                "individual_attack": individual_attack,
                "individual_defense": individual_defense,
                "individual_stamina": individual_stamina,
                "move_1": move_1,
                "move_2": move_2,
                "cp": cp,
                "cp_multiplier": cp_multiplier,
                "gender": gender,
                "form": form,
                "costume": costume,
                "height": height,
                "weight": weight,
                "weather_boosted_condition": weather_boosted_condition,
                "base_catch": catch_prob_1,
                "great_catch": catch_prob_2,
                "ultra_catch": catch_prob_3,
                "spawn_verified": verified == 1
            })
        return ret
