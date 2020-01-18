from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 18'

    def _execute(self):
        query = (
            "ALTER TABLE `trs_status` CHANGE `instance` `instance` VARCHAR(50) CHARACTER "
            "SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;"
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
