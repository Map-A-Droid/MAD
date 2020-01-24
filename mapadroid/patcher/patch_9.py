from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 9'

    def _execute(self):
        alter_query = (
            "UPDATE trs_quest "
            "SET quest_condition=REPLACE(quest_condition,'\\\"','\"'),"
            " quest_reward=REPLACE(quest_reward,'\\\"','\"')"
        )
        try:
            self._db.execute(alter_query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
