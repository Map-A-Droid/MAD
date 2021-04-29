from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add fort_id, cell_id and seen_type column to pokemon table'
    descr = 'Used for nearby scanning'

    def _execute(self):
        alter_pokemon = """
            ALTER TABLE `pokemon`
            ADD COLUMN `fort_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL;
        """
        try:
            if not self._schema_updater.check_column_exists("pokemon", "fort_id"):
                self._db.execute(alter_pokemon, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True


        add_enums_cell = (
            "ALTER TABLE `pokemon` "
            "ADD COLUMN `cell_id` bigint(20) unsigned DEFAULT NULL, "
            "ADD COLUMN `seen_type` enum('wild', 'encounter', "
            "'nearby_stop', 'nearby_cell', 'lure_wild', 'lure_encounter');"
        )

        try:
            if not self._schema_updater.check_column_exists("pokemon", "seen_type"):
                self._db.execute(add_enums_cell, commit=True, raise_exec=True)
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