from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add add_is_ar_scan_eligible flag to pokestop and gyms'
    descr = 'New Protos, more useless data!'

    def _execute(self):
        alter_pokestop = """
            ALTER TABLE `pokestop`
            ADD COLUMN `is_ar_scan_eligible` tinyint(1) NOT NULL DEFAULT '0';
        """
        try:
            if not self._schema_updater.check_column_exists("pokestop", "is_ar_scan_eligible"):
                self._db.execute(alter_pokestop, commit=True, raise_exc=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

        alter_gym = """
            ALTER TABLE `gym`
            ADD COLUMN `is_ar_scan_eligible` tinyint(1) NOT NULL DEFAULT '0';
        """
        try:
            if not self._schema_updater.check_column_exists("gym", "is_ar_scan_eligible"):
                self._db.execute(alter_gym, commit=True, raise_exc=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
