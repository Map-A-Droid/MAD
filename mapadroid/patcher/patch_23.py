from ._patch_base import PatchBase

class Patch(PatchBase):
    name = 'Create view for status page'
    def _execute(self):
        # Store as TIMESTAMP as it will handle everything with epoch
        fields = ['lastProtoDateTime', 'lastPogoRestart', 'lastPogoReboot']
        for field in fields:
            sql = "ALTER TABLE `trs_status` CHANGE `%s` `%s` TIMESTAMP NULL DEFAULT NULL;"
            try:
                self._db.execute(sql % (field, field,), commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
        # Add an idle identifier since we can no longer set area names
        sql = 'ALTER TABLE `trs_status` ADD `idle` TINYINT NULL DEFAULT 0 AFTER `area_id`;'
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
        sql = """
            CREATE VIEW `v_trs_status` AS
                SELECT trs.`device_id`, dev.`name`, trs.`routePos`, trs.`routeMax`, trs.`area_id`,
                IF(trs.`idle` = 1, 'Idle', IFNULL(sa.`name`, 'Idle')) AS 'rmname',
                IF(trs.`idle` = 1, 'Idle', IFNULL(sa.`mode`, 'Idle')) AS 'mode',
                trs.`rebootCounter`, trs.`init`, trs.`currentSleepTime`,
                trs.`rebootingOption`, trs.`restartCounter`, trs.`globalrebootcount`, trs.`globalrestartcount`,
                UNIX_TIMESTAMP(trs.`lastPogoRestart`) AS 'lastPogoRestart',
                UNIX_TIMESTAMP(trs.`lastProtoDateTime`) AS 'lastProtoDateTime',
                UNIX_TIMESTAMP(trs.`lastPogoReboot`) AS 'lastPogoReboot',
                CONCAT(ROUND(ST_X(trs.`currentPos`), 5), ', ', ROUND(ST_Y(trs.`currentPos`), 5)) AS 'currentPos',
                CONCAT(ROUND(ST_X(trs.`lastPos`), 5), ', ', ROUND(ST_Y(trs.`lastPos`), 5)) AS 'lastPos',
                `currentPos` AS 'currentPos_raw',
                `lastPos` AS 'lastPos_raw'
                FROM `trs_status` trs
                INNER JOIN `settings_device` dev ON dev.`device_id` = trs.`device_id`
                LEFT JOIN `settings_area` sa ON sa.`area_id` = trs.`area_id`
            """
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
