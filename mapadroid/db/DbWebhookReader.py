from datetime import datetime, timezone

from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbWebhookReader:

    def __init__(self, db_exec: PooledQueryExecutor, db_wrapper):
        self._db_exec: PooledQueryExecutor = db_exec
        # TODO: DbWrapper is currently required because `dbWrapper.quests_from_db` is shared between
        # map and webhook. Old typehinting used to avoid circular dependencies. This should be
        # resolved in future iterations.
        self._db_wrapper = db_wrapper

    def get_raids_changed_since(self, timestamp):
        logger.debug2("DbWebhookReader::get_raids_changed_since called")
        query = (
            "SELECT raid.gym_id, raid.level, raid.spawn, raid.start, raid.end, raid.pokemon_id, "
            "raid.cp, raid.move_1, raid.move_2, raid.last_scanned, raid.form, raid.is_exclusive, raid.gender, "
            "raid.costume, raid.evolution, gymdetails.name, gymdetails.url, gym.latitude, gym.longitude, "
            "gym.team_id, gym.weather_boosted_condition, gym.is_ex_raid_eligible "
            "FROM raid "
            "LEFT JOIN gymdetails ON gymdetails.gym_id = raid.gym_id "
            "LEFT JOIN gym ON gym.gym_id = raid.gym_id "
            "WHERE raid.last_scanned >= %s"
        )
        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (gym_id, level, spawn, start, end, pokemon_id,
             cp, move_1, move_2, last_scanned, form, is_exclusive, gender,
             costume, evolution, name, url, latitude, longitude, team_id,
             weather_boosted_condition, is_ex_raid_eligible) in res:
            ret.append({
                "gym_id": gym_id,
                "level": level,
                "spawn": int(spawn.replace(tzinfo=timezone.utc).timestamp()),
                "start": int(start.replace(tzinfo=timezone.utc).timestamp()),
                "end": int(end.replace(tzinfo=timezone.utc).timestamp()),
                "pokemon_id": pokemon_id,
                "cp": cp,
                "move_1": move_1,
                "move_2": move_2,
                "last_scanned": int(last_scanned.replace(tzinfo=timezone.utc).timestamp()),
                "form": form,
                "name": name,
                "url": url,
                "latitude": latitude,
                "longitude": longitude,
                "team_id": team_id,
                "weather_boosted_condition": weather_boosted_condition,
                "is_exclusive": is_exclusive,
                "gender": gender,
                "is_ex_raid_eligible": is_ex_raid_eligible,
                "costume": costume,
                "evolution": evolution
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

    def get_mon_changed_since(self, timestamp, mon_types=None):
        logger.debug2("DbWebhookReader::get_mon_changed_since called")
        if mon_types is None:
            mon_types = {"encounter", "lure_encounter"}
        query = (
            "SELECT pokemon.encounter_id, spawnpoint_id, pokemon_id, pokemon.latitude, pokemon.longitude, "
            "disappear_time, individual_attack, individual_defense, individual_stamina, "
            "move_1, move_2, cp, cp_multiplier, weight, height, pokemon.gender, pokemon.form, pokemon.costume, "
            "weather_boosted_condition, pokemon.last_modified, catch_prob_1, catch_prob_2, catch_prob_3, "
            "(trs_spawn.calc_endminsec IS NOT NULL) AS verified, seen_type, "
            "pokemon_display.pokemon as display_pokemon, "
            "pokemon_display.form as display_form, "
            "pokemon_display.costume as display_costume, "
            "pokemon_display.gender as display_gender, "
            "{}"
            "FROM pokemon "
            "LEFT JOIN trs_spawn ON pokemon.spawnpoint_id = trs_spawn.spawnpoint {} "
            "LEFT JOIN pokemon_display ON pokemon.encounter_id=pokemon_display.encounter_id "
            "WHERE pokemon.last_modified >= %s "
        )
        query_mon_types = ["'" + t + "'" for t in mon_types]
        query += "AND seen_type in (" + ",".join(query_mon_types) + ")"

        extra_select = ""
        extra_join = ""
        if {"nearby_stop", "lure_wild", "lure_encounter"} & mon_types:
            extra_select += "fort_id, pokestop.name, pokestop.image, "
            extra_join += "LEFT JOIN pokestop ON pokemon.fort_id = pokestop.pokestop_id "
        else:
            extra_select += "NULL, NULL, NULL, "

        if "nearby_cell" in mon_types:
            extra_select += "cell_id "
        else:
            extra_select += "NULL "

        query = query.format(extra_select, extra_join)

        tsdt = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        res = self._db_exec.execute(query, (tsdt,))

        ret = []
        for (encounter_id, spawnpoint_id, pokemon_id, latitude,
             longitude, disappear_time, individual_attack,
             individual_defense, individual_stamina, move_1, move_2,
             cp, cp_multiplier, weight, height, gender, form, costume,
             weather_boosted_condition, last_modified, catch_prob_1, catch_prob_2, catch_prob_3,
             verified, seen_type, display_pokemon, display_form, display_costume, display_gender,
             fort_id, stop_name, stop_url, cell_id) in res:

            if latitude == 0 and seen_type == "lure_encounter":
                continue

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
                "spawn_verified": verified == 1,
                "fort_id": fort_id,
                "stop_name": stop_name,
                "stop_url": stop_url,
                "cell_id": cell_id,
                "seen_type": seen_type,
                "display_pokemon": display_pokemon,
                "display_form": display_form,
                "display_costume": display_costume,
                "display_gender": display_gender
            })
        return ret
