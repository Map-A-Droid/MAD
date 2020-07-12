from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Origin Hopper'
    descr = 'Allows a device with the correct authentication to generate a new origin record'

    def _execute(self):
        origin_sql = """
            CREATE TABLE `origin_hopper` (
                `origin` VARCHAR(128) NOT NULL,
                `last_id` int UNSIGNED NOT NULL,
                PRIMARY KEY (`origin`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        try:
            self._db.execute(origin_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
