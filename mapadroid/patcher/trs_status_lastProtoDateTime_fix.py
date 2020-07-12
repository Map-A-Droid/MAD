from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Fix trs_status.lastProtoDateTime auto-update'

    def _execute(self):
        sql = "SELECT `EXTRA`\n"\
              "FROM `INFORMATION_SCHEMA`.`COLUMNS`\n"\
              "WHERE TABLE_SCHEMA = %s AND `TABLE_NAME` = 'trs_status'\n"\
              "AND `COLUMN_NAME` = 'lastProtoDateTime'"
        try:
            extra = self._db.autofetch_value(sql, (self._application_args.dbname))
            if extra:
                update = "ALTER TABLE `%s`.`trs_status`\n"\
                         "CHANGE `lastProtoDateTime`\n"\
                         "lastProtoDateTime TIMESTAMP NULL" % (self._application_args.dbname,)
                self._db.execute(update, args=(), commit=True, raise_exc=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
