from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 2'

    def _execute(self):
        alter_query = (
            "ALTER TABLE trs_quest "
            "CHANGE quest_reward "
            "quest_reward VARCHAR(1000) NULL DEFAULT NULL"
        )
        try:
            self._db.execute(alter_query, commit=True)
        except Exception as e:
            self._logger.info("Unexpected error: {}", e)
            self.issues = True
