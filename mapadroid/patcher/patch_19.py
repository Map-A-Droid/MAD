from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 19'

    def _execute(self):
        # Non-instanced devices in trs_status will cause the upgrade to fail.  Since these entries are prior
        # to bfbadcd we can remove them
        sql = "SELECT `origin` FROM `trs_status` WHERE `instance` = ''"
        bad_devs = self._db.autofetch_column(sql)
        if bad_devs:
            self._logger.warning('Found devices that have no instance.  These will be removed from the table. '
                                 '{}', bad_devs)
            del_data = {
                'instance': ''
            }
            self._db.autoexec_delete('trs_status', del_data)
        sql = "SELECT `DATA_TYPE`\n" \
              "FROM `INFORMATION_SCHEMA`.`COLUMNS`\n" \
              "WHERE `TABLE_NAME` = 'trs_status' AND `COLUMN_NAME` = 'instance'"
        res = self._db.autofetch_value(sql)
        if res:
            instances = {
                self._application_args.status_name: self._db.instance_id
            }
            # We dont want to mess with collations so just pull in and compare
            sql = "SELECT `instance`, `origin` FROM `trs_status`"
            try:
                devs = self._db.autofetch_all(sql)
                if devs is None:
                    devs = []
            except Exception:
                devs = []
            for dev in devs:
                if dev['instance'] not in instances:
                    tmp_instance = self._db.get_instance_id(instance_name=dev['instance'])
                    instances[dev['instance']] = tmp_instance
                update_data = {
                    'instance_id': instances[dev['instance']]
                }
                try:
                    self._db.autoexec_update('trs_status', update_data, where_keyvals=dev, suppress_issue=True,
                                             raise_exec=True)
                except Exception:
                    self._logger.warning('Unable to set {}', update_data)
            # Drop the old column
            alter_query = (
                "ALTER TABLE trs_status "
                "DROP instance"
            )
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
