from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Implement MADROM Auto-configuration w/ wifi'

    def _execute(self):
        try:
            sql = "ALTER TABLE `settings_device`\n"\
                  "     ADD `wifi_mac_address` VARCHAR(17) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL\n"\
                  "     AFTER `mac_address`;"
            self._db.execute(sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
