from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add has_pokemon to trs_s2cells'
    descr = 'Used to refine routes for use with nearby_cell mons'

    def _execute(self):
        alter_cells = """
            ALTER TABLE `trs_s2cells`
            ADD COLUMN `has_pokemon` tinyint(1) NOT NULL DEFAULT '0';
        """
        try:
            if not self._schema_updater.check_column_exists("trs_s2cells", "has_pokemon"):
                self._db.execute(alter_cells, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

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