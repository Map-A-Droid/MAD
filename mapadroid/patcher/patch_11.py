from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 11'

    def _execute(self):
        query = (
            "ALTER TABLE trs_stats_detect_raw "
            "ADD is_shiny TINYINT(1) NOT NULL DEFAULT '0' "
            "AFTER count"
        )
        column_exist = self._schema_updater.check_column_exists(
            'trs_stats_detect_raw', 'is_shiny')
        if not column_exist:
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
