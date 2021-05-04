from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Removed has_pokemon from trs_s2cell'
    descr = 'Temporary column for a PR'

    def _execute(self):
        alter_cells = """
            ALTER TABLE `trs_s2cells`
            DROP COLUMN `has_pokemon`;
        """
        try:
            if self._schema_updater.check_column_exists("trs_s2cells", "has_pokemon"):
                self._db.execute(alter_cells, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True