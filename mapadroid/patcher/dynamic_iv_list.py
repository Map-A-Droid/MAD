from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Enable dynamic IV list for mons. This allows for non-selected priority mons to be scanned in ID order'
    descr = 'Less clicky more usefulness!'

    def _execute(self):
        tables = ["settings_area_iv_mitm", "settings_area_mon_mitm", "settings_area_raids_mitm"]
        for table in tables:
            if not self._schema_updater.check_column_exists(table, "all_mons"):
                alter = """
                    ALTER TABLE `{}`
                    ADD COLUMN `all_mons` tinyint(1) NOT NULL DEFAULT '0';
                    AFTER `monlist_id`
                """.format(table)
                try:
                    self._db.execute(alter, commit=True, raise_exec=True)
                except Exception as e:
                    self._logger.exception("Unexpected error: {}", e)
                    self.issues = True
