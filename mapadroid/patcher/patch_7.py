from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 7'

    def _execute(self):
        alter_query = (
            "ALTER TABLE trs_status "
            "ADD lastPogoReboot varchar(50) NULL DEFAULT NULL"
        )
        column_exist = self._schema_updater.check_column_exists(
            'trs_status', 'lastPogoReboot')
        if not column_exist:
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
        alter_query = (
            "ALTER TABLE trs_status "
            "ADD globalrebootcount int(11) NULL DEFAULT '0'"
        )
        column_exist = self._schema_updater.check_column_exists(
            'trs_status', 'globalrebootcount')
        if not column_exist:
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
        alter_query = (
            "ALTER TABLE trs_status "
            "ADD globalrestartcount int(11) NULL DEFAULT '0'"
        )
        column_exist = self._schema_updater.check_column_exists(
            'trs_status', 'globalrestartcount')
        if not column_exist:
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
        alter_query = (
            "ALTER TABLE trs_status CHANGE lastPogoRestart "
            "lastPogoRestart VARCHAR(50) NULL DEFAULT NULL"
        )
        try:
            self._db.execute(alter_query, commit=True)
        except Exception as e:
            self._logger.info("Unexpected error: {}", e)
            self.issues = True
        alter_query = (
            "ALTER TABLE trs_status "
            "CHANGE currentPos currentPos VARCHAR(50) NULL DEFAULT NULL, "
            "CHANGE lastPos lastPos VARCHAR(50) NULL DEFAULT NULL, "
            "CHANGE routePos routePos INT(11) NULL DEFAULT NULL, "
            "CHANGE routeMax routeMax INT(11) NULL DEFAULT NULL, "
            "CHANGE rebootingOption rebootingOption TEXT NULL, "
            "CHANGE rebootCounter rebootCounter INT(11) NULL DEFAULT NULL, "
            "CHANGE routemanager routemanager VARCHAR(255) NULL DEFAULT NULL, "
            "CHANGE lastProtoDateTime lastProtoDateTime VARCHAR(50), "
            "CHANGE lastPogoRestart lastPogoRestart VARCHAR(50), "
            "CHANGE init init TEXT NULL, "
            "CHANGE restartCounter restartCounter TEXT NULL"
        )
        try:
            self._db.execute(alter_query, commit=True)
        except Exception as e:
            self._logger.info("Unexpected error: {}", e)
            self.issues = True
