from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add trs_stats_detect_seen_type table'
    descr = 'For first_seen times of different mon types'

    def _execute(self):
        query = (
            "CREATE TABLE IF NOT EXISTS `trs_stats_detect_seen_type` ( "
            "`encounter_id` bigint(20) unsigned NOT NULL, "
            "`encounter` datetime DEFAULT NULL, "
            "`wild` datetime DEFAULT NULL, "
            "`nearby_stop` datetime DEFAULT NULL, "
            "`nearby_cell` datetime DEFAULT NULL, "
            "`lure_encounter` datetime DEFAULT NULL, "
            "`lure_wild` datetime DEFAULT NULL, "
            "PRIMARY KEY (`encounter_id`) "
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
