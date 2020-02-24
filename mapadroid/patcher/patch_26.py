from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 26 - MAD Event - add default value'

    def _execute(self):
        sql = "Insert into `trs_event` "\
              "(`event_name`, `event_start`, `event_end`) values "\
              "('DEFAULT', '1970-01-01', '2099-12-31')"
        try:
            self._db.execute(sql, commit=True, suppress_log=False)
        except Exception:
            pass

        if not self._schema_updater.check_column_exists('trs_spawn', 'eventid'):
            query = (
                "ALTER TABLE trs_spawn "
                "ADD eventid INT(11) NOT NULL DEFAULT 1"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
