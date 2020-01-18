from ._patch_base import PatchBase

class Patch(PatchBase):
    name = 'Patch 20'
    def _execute(self):
        sql = "ALTER TABLE versions ADD PRIMARY KEY(`key`)"
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
