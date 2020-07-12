from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 26 - MAD Event - add default value'

    def _execute(self):
        if not self._schema_updater.check_column_exists('trs_spawn', 'eventid'):
            query = (
                "ALTER TABLE trs_spawn "
                "ADD eventid INT(11) NOT NULL DEFAULT 1"
            )
            try:
                self._db.execute(query, commit=True, raise_exc=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        if not self._schema_updater.check_column_exists('settings_walkerarea', 'eventid'):
            query = (
                "ALTER TABLE settings_walkerarea "
                "ADD eventid INT DEFAULT NULL"
            )
            try:
                self._db.execute(query, commit=True, raise_exc=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        sql = """CREATE TABLE IF NOT EXISTS `trs_event` (
                    `id` int(11) NOT NULL AUTO_INCREMENT,
                    `event_name` varchar(100),
                    `event_start`datetime,
                    `event_end` datetime,
                    `event_lure_duration` int NOT NULL DEFAULT 30,
                    PRIMARY KEY (`id`)
                    )"""
        try:
            self._db.execute(sql, commit=True, raise_exc=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

        sql = "INSERT IGNORE into `trs_event` " \
              "(`id`, `event_name`, `event_start`, `event_end`, `event_lure_duration`) values " \
              "('1', 'DEFAULT', '1970-01-01', '2099-12-31', 30)"
        try:
            self._db.execute(sql, commit=True, suppress_log=False, raise_exc=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True

        if not self._schema_updater.check_column_exists('settings_area_mon_mitm', 'include_event_id'):
            query = (
                "ALTER TABLE settings_area_mon_mitm "
                "ADD include_event_id INT DEFAULT NULL"
            )
            try:
                self._db.execute(query, commit=True, raise_exc=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
