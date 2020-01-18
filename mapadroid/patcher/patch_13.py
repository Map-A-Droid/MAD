from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 13'

    def _execute(self):
        # Adding current_sleep for worker status
        if not self._schema_updater.check_column_exists('trs_status', 'currentSleepTime'):
            query = (
                "ALTER TABLE trs_status "
                "ADD currentSleepTime INT(11) NOT NULL DEFAULT 0"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
