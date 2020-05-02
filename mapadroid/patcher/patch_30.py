from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add enhanced mode column'

    def _execute(self):
        # Adding column enhanced_mode_quest for devicepool
        if not self._schema_updater.check_column_exists('settings_devicepool', 'enhanced_mode_quest'):
            query = (
                "ALTER TABLE settings_devicepool "
                "ADD enhanced_mode_quest TINYINT(1) NULL DEFAULT 0"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        # Adding column enhanced_mode_quest for device
        if not self._schema_updater.check_column_exists('settings_device', 'enhanced_mode_quest'):
            query = (
                "ALTER TABLE settings_device "
                "ADD enhanced_mode_quest TINYINT(1) NULL DEFAULT 0"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
