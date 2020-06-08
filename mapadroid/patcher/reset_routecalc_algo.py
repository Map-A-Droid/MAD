from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Reset routcalc algorithm'
    descr = 'Resets the routecalc algorithm for all pokestop routes to fallback to "quick".'

    def _execute(self):
        origin_sql = "UPDATE settings_area_pokestops SET route_calc_algorithm=NULL"
        try:
            self._db.execute(origin_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
