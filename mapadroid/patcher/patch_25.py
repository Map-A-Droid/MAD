from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 25 - MADmin APK Cleanup'

    def _execute(self):
        # The key was incorrectly named a foreign key (fk).  Renaming to key (k)
        sql = "ALTER TABLE `filestore_chunks` "\
              "DROP INDEX `fk_fs_chunks`, "\
              "ADD INDEX `k_fs_chunks` (`filestore_id`)"
        try:
            self._db.execute(sql, commit=True, suppress_log=True)
        except Exception:
            pass
        # There was an issue where the chunk table was not being cleaned up.  Remove any chunks whose filestore_id
        # no longer exists
        sql = "DELETE fc\n"\
              "FROM `filestore_chunks` fc\n"\
              "LEFT JOIN `filestore_meta` fm ON fm.`filestore_id` = fc.`filestore_id`\n"\
              "WHERE fm.`filestore_id` IS NULL"
        try:
            self._db.execute(sql, commit=True)
        except Exception:
            pass
        sql = "DELETE fm\n"\
              "FROM `filestore_meta` fm\n"\
              "LEFT JOIN `mad_apks` ma ON ma.`filestore_id` = fm.`filestore_id`\n"\
              "WHERE ma.`filestore_id` IS NULL"
        try:
            self._db.execute(sql, commit=True)
        except Exception:
            pass
