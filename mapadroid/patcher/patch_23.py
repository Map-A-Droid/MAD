from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Update trs_status'

    def _execute(self):
        sql = "SELECT COUNT(*) FROM `information_schema`.`views` WHERE `TABLE_NAME` = 'v_trs_status'"
        count = self._db.autofetch_value(sql)
        # We only want to perform the update if the view doesnt exist.  Prevent the bad queries against incorrect
        # table structures
        if not count:
            existing_data = {}
            sql = "SELECT trs.`instance_id`, trs.`origin`, trs.`currentPos`, trs.`lastPos`, trs.`routePos`,"\
                  "trs.`routeMax`, trs.`routemanager`, trs.`rebootCounter`, trs.`lastProtoDateTime`,"\
                  "trs.`lastPogoRestart`, trs.`init`, trs.`rebootingOption`, trs.`restartCounter`,"\
                  "trs.`globalrebootcount`, trs.`globalrestartcount`, trs.`lastPogoReboot`, trs.`currentSleepTime`\n"\
                  "FROM `trs_status` trs"
            try:
                existing_data = self._db.autofetch_all(sql, raise_exec=True)
            except Exception:
                pass
            if not existing_data:
                existing_data = {}
            sql = "DROP TABLE IF EXISTS `trs_status`"
            try:
                self._db.execute(sql, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
            new_table = """
                CREATE TABLE `trs_status` (
                 `instance_id` INT UNSIGNED NOT NULL,
                 `device_id` INT UNSIGNED NOT NULL,
                 `currentPos` POINT DEFAULT NULL,
                 `lastPos` POINT DEFAULT NULL,
                 `routePos` INT DEFAULT NULL,
                 `routeMax` INT DEFAULT NULL,
                 `area_id` INT UNSIGNED DEFAULT NULL,
                 `idle` TINYINT NULL DEFAULT 0,
                 `rebootCounter` INT DEFAULT NULL,
                 `lastProtoDateTime` TIMESTAMP,
                 `lastPogoRestart` TIMESTAMP,
                 `init` TINYINT(1) DEFAULT NULL,
                 `rebootingOption` TINYINT(1) DEFAULT NULL,
                 `restartCounter` INT DEFAULT NULL,
                 `lastPogoReboot` TIMESTAMP,
                 `globalrebootcount` INT DEFAULT 0,
                 `globalrestartcount` INT DEFAULT 0,
                 `currentSleepTime` INT NOT NULL DEFAULT 0,
                 PRIMARY KEY (`device_id`),
                 CONSTRAINT `fk_ts_dev_id`
                    FOREIGN KEY (`device_id`)
                    REFERENCES `settings_device` (`device_id`)
                    ON DELETE CASCADE,
                 CONSTRAINT `fk_ts_instance`
                     FOREIGN KEY (`instance_id`)
                     REFERENCES `madmin_instance` (`instance_id`)
                     ON DELETE CASCADE,
                 CONSTRAINT `fk_ts_areaid`
                     FOREIGN KEY (`area_id`)
                     REFERENCES `settings_area` (`area_id`)
                     ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            try:
                self._db.execute(new_table, commit=True, raise_exec=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
            point_fields = ['currentPos', 'lastPos']
            bool_fields = ['rebootingOption', 'init']
            for row in existing_data:
                dev_id_sql = "SELECT `device_id` FROM `settings_device` WHERE `name` = %s and `instance_id` = %s"
                dev_id = self._db.autofetch_value(dev_id_sql, args=(row['origin'], row['instance_id']))
                del row['origin']
                row['device_id'] = dev_id
                try:
                    row['area_id'] = int(row['routemanager'])
                    if row['area_id'] == 0:
                        self._logger.warning('Detected a device that has a routemanager of 0.  Skipping due to '
                                             'foreign key issues {}', row)
                        continue
                    del row['routemanager']
                except Exception:
                    continue
                for field in point_fields:
                    if not row[field]:
                        continue
                    point = row[field].split(",")
                    row[field] = "POINT(%s,%s)" % (point[0], point[1])
                for field in bool_fields:
                    if not row[field]:
                        continue
                    row[field] = 0 if row[field].lower() == 'false' else 1
                self._db.autoexec_insert('trs_status', row, literals=point_fields, raise_exec=True)
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
                self._db.execute(sql, commit=True, raise_exec=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
