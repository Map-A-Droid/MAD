from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 10'

    def _execute(self):
        query = (
            "CREATE TABLE IF NOT EXISTS trs_s2cells ( "
            "id bigint(20) unsigned NOT NULL, "
            "level int(11) NOT NULL, "
            "center_latitude double NOT NULL, "
            "center_longitude double NOT NULL, "
            "updated int(11) NOT NULL, "
            "PRIMARY KEY (id)) "
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
