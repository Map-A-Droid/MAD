from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 8'

    def _execute(self):
        alter_query = (
            "ALTER TABLE trs_quest "
            "ADD quest_template VARCHAR(100) NULL DEFAULT NULL "
            "AFTER quest_reward"
        )
        column_exist = self._schema_updater.check_column_exists(
            'trs_quest', 'quest_template')
        if not column_exist:
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
