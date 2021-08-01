from ._patch_base import PatchBase


class Patch(PatchBase):
    name = "Pokestop Encounters"
    descr = (
        'Add settings to enable encounters in pokestop mode'
    )

    def _execute(self):
        if not self._schema_updater.check_column_exists("settings_area_pokestops", "all_mons"):
            alter = """
                ALTER TABLE `settings_area_pokestops`
                ADD COLUMN `all_mons` tinyint(1) NOT NULL DEFAULT '0'
            """
            try:
                self._db.execute(alter, commit=True, raise_exc=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

        if not self._schema_updater.check_column_exists("settings_area_pokestops", "monlist_id"):
            alter = """
                ALTER TABLE `settings_area_pokestops`
                ADD COLUMN `monlist_id` int(10) unsigned DEFAULT NULL,
                ADD KEY `fk_ap_monid` (`monlist_id`),
                ADD CONSTRAINT `fk_ap_monid` FOREIGN KEY (`monlist_id`)
                    REFERENCES `settings_monivlist` (`monlist_id`);
            """
            try:
                self._db.execute(alter, commit=True, raise_exc=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
