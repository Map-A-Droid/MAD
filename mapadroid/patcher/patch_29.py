from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Routefree algo for quest/level mode'
    descr = 'Adds routefree algo mode'

    def _execute(self):
        origin_sql = """
            ALTER TABLE `settings_area_pokestops`
            CHANGE COLUMN `route_calc_algorithm`
            `route_calc_algorithm` ENUM('optimized', 'quick', 'routefree')
            CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL;
        """
        try:
            self._db.execute(origin_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
