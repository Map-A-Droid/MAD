from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Modify a bunch of tables to allow new ways to scan Mons'
    descr = (
        "- add fort_id, cell_id, seen_type to pokemon. "
        "- remove encounter_id from pokestop (a bug). "
        "- Create trs_stats_detect_seen_type stats table. "
    )

    def _execute(self):
        self._logger.warning("This migration may take a while if you don't trim your pokemon table.")
        alter_pokemon = (
            "ALTER TABLE `pokemon` "
            "ADD COLUMN `fort_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL, "
            "ADD COLUMN `cell_id` bigint(20) unsigned DEFAULT NULL, "
            "ADD COLUMN `seen_type` enum('wild', 'encounter', "
            "'nearby_stop', 'nearby_cell', 'lure_wild', 'lure_encounter');"
        )
        try:
            if not self._schema_updater.check_column_exists("pokemon", "fort_id")\
                    or not self._schema_updater.check_column_exists("pokemon", "cell_id")\
                    or not self._schema_updater.check_column_exists("pokemon", "seen_type"):
                self._db.execute(alter_pokemon, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

        remove_encounter_id = """
            ALTER TABLE `pokestop`
            DROP COLUMN `encounter_id`;
        """
        try:
            if self._schema_updater.check_column_exists("pokestop", "encounter_id"):
                self._db.execute(remove_encounter_id, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

        query = (
            "CREATE TABLE IF NOT EXISTS `trs_stats_detect_seen_type` ( "
            "`encounter_id` bigint(20) unsigned NOT NULL, "
            "`encounter` datetime NULL DEFAULT NULL, "
            "`wild` datetime NULL DEFAULT NULL, "
            "`nearby_stop` datetime NULL DEFAULT NULL, "
            "`nearby_cell` datetime NULL DEFAULT NULL, "
            "`lure_encounter` datetime NULL DEFAULT NULL, "
            "`lure_wild` datetime NULL DEFAULT NULL, "
            "PRIMARY KEY (`encounter_id`) "
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
