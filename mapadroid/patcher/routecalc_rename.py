from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Change available routecalc algorithms'
    descr = 'Replace optimized/quick algos with just "route"'

    def _execute(self):
        origin_sql = """
            ALTER TABLE `settings_area_pokestops`
            CHANGE COLUMN `route_calc_algorithm`
            `route_calc_algorithm` ENUM('route', 'routefree')
            CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL ;
        """
        try:
            self._db.execute(origin_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
