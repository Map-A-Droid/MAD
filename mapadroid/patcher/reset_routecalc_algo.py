from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Reset roalc algorithm'
    descr = 'Resets the routecalc algorithm for all pokestop routes to fallback to "quick".'

    def _execute(self):
        sql = (
            "UPDATE settings_area_pokestops "
            "SET route_calc_algorithm=NULL "
            "WHERE route_calc_algorithm != 'routefree'"
        )

        try:
            await self._run_raw_sql_query(sql)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
