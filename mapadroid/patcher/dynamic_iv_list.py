from ._patch_base import PatchBase


class Patch(PatchBase):
    name = "Dynamic IV Lists"
    descr = (
        'Enable dynamic IV list for mons which allows for mons to be scanned not on an IV list. If a mon is not on the '
        'IV list it will be added to the list based on mon id'
    )

    def _execute(self):
        tables = ["settings_area_iv_mitm", "settings_area_mon_mitm", "settings_area_raids_mitm"]
        for table in tables:
            if not self._schema_updater.check_column_exists(table, "all_mons"):
                alter = """
                    ALTER TABLE `{}`
                    ADD COLUMN `all_mons` tinyint(1) NOT NULL DEFAULT '0'
                    AFTER `monlist_id`;
                """.format(table)
                try:
                    self._db.execute(alter, commit=True, raise_exc=True)
                except Exception as e:
                    self._logger.exception("Unexpected error: {}", e)
                    self.issues = True
