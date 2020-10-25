from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add clear_route_every_time'
    descr = 'Add setting for clear_route_every_time to settings for pokestop area'

    def _execute(self):
        origin_sql = """
            ALTER TABLE `settings_area_pokestops`
            ADD COLUMN `clear_route_every_time` tinyint(0) not null default 0;
        """
        try:
            self._db.execute(origin_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
