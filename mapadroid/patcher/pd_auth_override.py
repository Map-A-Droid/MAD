from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Implement MADROM Auto-configuration'

    def _execute(self):
        # This is odd and it shouldnt occur.  Some fields were missing in
        # master sql so we need to re-run that patch that applied them
        try:
            if not self._schema_updater.check_column_exists('settings_device', 'pd_auth_override'):
                sql = "ALTER TABLE `settings_device`\n"\
                      " ADD `pd_auth_override` VARCHAR(128) CHARACTER SET 'utf8mb4' "\
                      " COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                      " AFTER `enhanced_mode_quest_safe_items`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_devicepool', 'pd_auth_override'):
                sql = "ALTER TABLE `settings_devicepool`\n"\
                      " ADD `pd_auth_override` VARCHAR(128) CHARACTER SET 'utf8mb4' "\
                      " COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                      " AFTER `enhanced_mode_quest_safe_items`;"
                self._db.execute(sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
