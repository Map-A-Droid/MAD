from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Implement the ability to override authentication for autoconfig'

    def _execute(self):
        try:
            if not self._schema_updater.check_column_exists('settings_device', 'pd_token_override'):
                sql = "ALTER TABLE `settings_device`\n"\
                      " ADD `pd_token_override` VARCHAR(128) CHARACTER SET 'utf8mb4' "\
                      " COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                      " AFTER `account_id`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_device', 'auth_id'):
                sql = "ALTER TABLE `settings_device`\n"\
                      " ADD `auth_id` int(10) unsigned DEFAULT NULL\n"\
                      " AFTER `pd_token_override`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_devicepool', 'pd_token_override'):
                sql = "ALTER TABLE `settings_devicepool`\n"\
                      " ADD `pd_token_override` VARCHAR(128) CHARACTER SET 'utf8mb4' "\
                      " COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                      " AFTER `enhanced_mode_quest_safe_items`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_devicepool', 'auth_id'):
                sql = "ALTER TABLE `settings_devicepool`\n"\
                      " ADD `auth_id` int(10) unsigned DEFAULT NULL\n"\
                      " AFTER `pd_token_override`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            sql = "ALTER TABLE `settings_device`\n"\
                  "     ADD CONSTRAINT `settings_device_ibfk_4`\n"\
                  "     FOREIGN KEY (`auth_id`)\n"\
                  "           REFERENCES `settings_auth` (`auth_id`);"
            self._db.execute(sql, commit=True, raise_exec=False)
            sql = "ALTER TABLE `settings_devicepool`\n"\
                  "     ADD CONSTRAINT `settings_devicepool_ibfk_1`\n"\
                  "     FOREIGN KEY (`auth_id`)\n"\
                  "           REFERENCES `settings_auth` (`auth_id`);"
            self._db.execute(sql, commit=True, raise_exec=False)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
