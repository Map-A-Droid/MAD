from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add nearby_cell_mode to settings_area_mon_mitm'
    descr = 'For mon_mitm'

    def _execute(self):
        alter_mon_mitm = """
            ALTER TABLE `settings_area_mon_mitm`
            ADD COLUMN `nearby_cell_mode` tinyint(1) DEFAULT NULL;
        """
        try:
            if not self._schema_updater.check_column_exists("settings_area_mon_mitm", "nearby_cell_mode"):
                self._db.execute(alter_mon_mitm, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
