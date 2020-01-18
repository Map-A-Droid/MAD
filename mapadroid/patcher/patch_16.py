from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 16'

    def _execute(self):
        query = (
            "CREATE TABLE IF NOT EXISTS `trs_visited` ("
            "`pokestop_id` varchar(50) NOT NULL collate utf8mb4_unicode_ci,"
            "`origin` varchar(50) NOT NULL collate utf8mb4_unicode_ci,"
            "PRIMARY KEY (`pokestop_id`,`origin`)"
            ")"
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
