from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Split trs_stats_detect_raw into mon and forts tables'

    def _execute(self):
        populate_mons = (
            "INSERT INTO trs_stats_detect_mon_raw (worker,encounter_id, `type`,`count`,is_shiny,timestamp_scan) "
            "SELECT worker,CAST(type_id AS UNSIGNED INT),`type`,`count`,is_shiny,timestamp_scan "
            "FROM trs_stats_detect_raw WHERE trs_stats_detect_raw.type IN('mon','mon_iv')"
        )
        populate_forts = (
            "INSERT INTO trs_stats_detect_fort_raw (worker,guid,`type`,`count`,timestamp_scan)"
            "SELECT worker,type_id,`type`,`count`,timestamp_scan "
            "FROM trs_stats_detect_raw WHERE trs_stats_detect_raw.type IN('quest','raid')"
        )
        del_old_table = (
            "DROP TABLE trs_stats_detect_raw"
        )

        iv_attack = (
            "ALTER TABLE pokemon ADD KEY `individual_attack` (`individual_attack`)"
        )
        try:
            self._db.execute(populate_mons, commit=True)
            self._db.execute(populate_forts, commit=True)
            self._db.execute(del_old_table, commit=True)
            if not self._schema_updater.check_index_exists('pokemon', 'individual_attack'):
                self._db.execute(iv_attack, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
