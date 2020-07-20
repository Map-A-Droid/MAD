from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Implement MADROM Auto-configuration'

    def _execute(self):
        try:
            sql = "CREATE TABLE IF NOT EXISTS `autoconfig_registration` (\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `session_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
                  " `device_id` int(10) unsigned NULL,\n"\
                  " `ip` varchar(39) NOT NULL,\n"\
                  " `name` varchar(128) COLLATE utf8mb4_unicode_ci NULL,\n"\
                  " `walker_id` int(10) unsigned NULL,\n"\
                  " `pool_id` int(10) unsigned NULL,\n"\
                  " `status` int(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,\n"\
                  " `locked` tinyint(1) NOT NULL DEFAULT 0,\n"\
                  " PRIMARY KEY (`session_id`),\n"\
                  " CONSTRAINT `fk_ac_r_instance` FOREIGN KEY (`instance_id`)\n"\
                  "   REFERENCES `madmin_instance` (`instance_id`)\n"\
                  "   ON DELETE CASCADE,\n"\
                  " CONSTRAINT `fk_ac_r_device` FOREIGN KEY (`device_id`)\n"\
                  "  REFERENCES `settings_device` (`device_id`)\n"\
                  "  ON DELETE CASCADE,\n"\
                  " CONSTRAINT `fk_ac_r_walker` FOREIGN KEY (`walker_id`)\n"\
                  "  REFERENCES `settings_walker` (`walker_id`),\n"\
                  " CONSTRAINT `fk_ac_r_pool` FOREIGN KEY (`pool_id`)\n"\
                  "  REFERENCES `settings_devicepool` (`pool_id`)\n"\
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

            sql = "CREATE TABLE IF NOT EXISTS`autoconfig_google` (\n"\
                  " `instance_id` int(10) unsigned NOT NULL,\n"\
                  " `email_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
                  " `email` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " `pwd` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
                  " `device_id` int(10) unsigned NULL,\n"\
                  " PRIMARY KEY (`email_id`),\n"\
                  " CONSTRAINT `fk_ac_g_instance` FOREIGN KEY (`instance_id`)\n"\
                  "  REFERENCES `madmin_instance` (`instance_id`)\n"\
                  "  ON DELETE CASCADE\n"\
                  ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            self._db.execute(sql, commit=True, raise_exc=True)

            sql = "ALTER TABLE `settings_device`\n"\
                  "     ADD `mac_address` VARCHAR(17) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                  "     AFTER `enhanced_mode_quest_safe_items`;"
            self._db.execute(sql, commit=True, raise_exec=True)
            sql = "ALTER TABLE `settings_device`\n"\
                  "     ADD `last_mac` VARCHAR(17) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                  "     AFTER `mac_address`;"
            self._db.execute(sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
