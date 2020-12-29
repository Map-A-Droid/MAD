import importlib
import sys

from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Implement MADROM Auto-configuration'

    def _execute(self):
        # This is odd and it shouldnt occur.  Some fields were missing in
        # master sql so we need to re-run that patch that applied them
        patch_base = importlib.import_module('mapadroid.patcher.patch_30')
        try:
            patch = patch_base.Patch(self._logger, self._db, self._data_manager, self._application_args)
            if patch.completed and not patch.issues:
                self._logger.success('Validating / Installed patch_30 was applied')
            else:
                self._logger.fatal('patch_30 was unsuccessful.  Please use your help channel for assistance')
                sys.exit(1)
        except Exception:
            self._logger.opt(exception=True).error('Patch was unsuccessful.  Exiting')
            sys.exit(1)
        try:
            sql = "CREATE TABLE IF NOT EXISTS `autoconfig_registration` (\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `session_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
                  " `device_id` int(10) unsigned NULL,\n"\
                  " `ip` varchar(39) NOT NULL,\n"\
                  " `status` int(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,\n"\
                  " PRIMARY KEY (`session_id`),\n"\
                  " CONSTRAINT `fk_ac_r_instance` FOREIGN KEY (`instance_id`)\n"\
                  "   REFERENCES `madmin_instance` (`instance_id`)\n"\
                  "   ON DELETE CASCADE,\n"\
                  " CONSTRAINT `fk_ac_r_device` FOREIGN KEY (`device_id`)\n"\
                  "  REFERENCES `settings_device` (`device_id`)\n"\
                  "  ON DELETE CASCADE\n"\
                  ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            self._db.execute(sql, commit=True, raise_exc=True)

            sql = "CREATE TABLE IF NOT EXISTS `autoconfig_file` (\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " `data` longblob NOT NULL,\n"\
                  " PRIMARY KEY (`instance_id`, `name`),\n"\
                  " CONSTRAINT `fk_ac_f_instance` FOREIGN KEY (`instance_id`)\n"\
                  "   REFERENCES `madmin_instance` (`instance_id`)\n"\
                  "   ON DELETE CASCADE\n"\
                  ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            self._db.execute(sql, commit=True, raise_exc=True)

            sql = "CREATE TABLE IF NOT EXISTS `settings_pogoauth` (\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `account_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
                  " `login_type` enum('google','ptc') COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " `username` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " `password` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " PRIMARY KEY (`account_id`),\n"\
                  " CONSTRAINT `fk_ac_g_instance` FOREIGN KEY (`instance_id`)\n"\
                  "  REFERENCES `madmin_instance` (`instance_id`)\n"\
                  "  ON DELETE CASCADE,\n"\
                  " CONSTRAINT `settings_pogoauth_u1` UNIQUE (`login_type`, `username`)\n"\
                  ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            self._db.execute(sql, commit=True, raise_exc=True)

            sql = "CREATE TABLE IF NOT EXISTS `autoconfig_logs` (\n"\
                  " `log_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `session_id` int(10) unsigned NOT NULL,\n"\
                  " `log_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,\n"\
                  " `level` int(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 2,\n"\
                  " `msg` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " PRIMARY KEY (`log_id`),\n"\
                  " KEY `k_acl` (`instance_id`, `session_id`),\n"\
                  " CONSTRAINT `fk_ac_l_instance` FOREIGN KEY (`session_id`)\n"\
                  "  REFERENCES `autoconfig_registration` (`session_id`)\n"\
                  "  ON DELETE CASCADE\n"\
                  ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            self._db.execute(sql, commit=True, raise_exc=True)

            if not self._schema_updater.check_column_exists('settings_device', 'mac_address'):
                sql = "ALTER TABLE `settings_device`\n"\
                      " ADD `mac_address` VARCHAR(17) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                      " AFTER `enhanced_mode_quest_safe_items`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_device', 'interface_type'):
                sql = "ALTER TABLE `settings_device`\n"\
                      " ADD `interface_type` enum('lan','wlan') COLLATE utf8mb4_unicode_ci DEFAULT 'lan'\n"\
                      " AFTER `mac_address`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            if not self._schema_updater.check_column_exists('settings_device', 'account_id'):
                sql = "ALTER TABLE `settings_device`\n"\
                      "     ADD `account_id` int(10) unsigned NULL\n"\
                      "     AFTER `interface_type`;"
                self._db.execute(sql, commit=True, raise_exec=True)
            sql = "ALTER TABLE `settings_device`\n"\
                  "     ADD CONSTRAINT `settings_device_ibfk_3`\n"\
                  "     FOREIGN KEY (`account_id`)\n"\
                  "           REFERENCES `settings_pogoauth` (`account_id`);"
            self._db.execute(sql, commit=True, raise_exec=False)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
