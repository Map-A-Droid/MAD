from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 12'

    def _execute(self):
        if self._schema_updater.check_index_exists('trs_stats_detect_raw', 'typeworker'):
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "DROP INDEX typeworker, "
                "ADD INDEX typeworker (worker, type_id)"
            )
        else:
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "ADD INDEX typeworker (worker, type_id)"
            )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
        if self._schema_updater.check_index_exists('trs_stats_detect_raw', 'shiny'):
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "DROP INDEX shiny, "
                "ADD INDEX shiny (is_shiny)"
            )
        else:
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "ADD INDEX shiny (is_shiny)"
            )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
