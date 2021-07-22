from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add encounter_all column to mon_mitm, iv_mitm, raids_mitm'

    async def _execute(self):
        # Adding column encounter_all for settings_area_mon_mitm
        if not self._schema_updater.check_column_exists('settings_area_mon_mitm', 'encounter_all'):
            query = (
                "ALTER TABLE settings_area_mon_mitm "
                "ADD encounter_all TINYINT(1) DEFAULT NULL"
            )
            try:
                await self._run_raw_sql_query(query)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        # Adding column encounter_all for settings_area_iv_mitm
        if not self._schema_updater.check_column_exists('settings_area_iv_mitm', 'encounter_all'):
            query = (
                "ALTER TABLE settings_area_iv_mitm "
                "ADD encounter_all TINYINT(1) DEFAULT NULL"
            )
            try:
                await self._run_raw_sql_query(query)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        # Adding column encounter_all for settings_area_raids_mitm
        if not self._schema_updater.check_column_exists('settings_area_raids_mitm', 'encounter_all'):
            query = (
                "ALTER TABLE settings_area_raids_mitm "
                "ADD encounter_all TINYINT(1) DEFAULT NULL"
            )
            try:
                await self._run_raw_sql_query(query)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
