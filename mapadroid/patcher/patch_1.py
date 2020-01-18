from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 1'

    def _execute(self):
        # Adding quest_reward for PMSF ALT
        if not self._schema_updater.check_column_exists('trs_quest', 'quest_reward'):
            alter_query = (
                "ALTER TABLE trs_quest "
                "ADD quest_reward VARCHAR(500) NULL AFTER quest_condition"
            )
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
        # Adding quest_task = ingame quest conditions
        if not self._schema_updater.check_column_exists('trs_quest', 'quest_task'):
            alter_query = (
                "ALTER TABLE trs_quest "
                "ADD quest_task VARCHAR(150) NULL AFTER quest_reward"
            )
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
        # Adding form column if it doesnt exist
        alter_query = (
            "ALTER TABLE raid "
            "ADD form smallint(6) DEFAULT NULL"
        )
        column_exist = self._schema_updater.check_column_exists(
            'raid', 'form')
        if not column_exist:
            try:
                self._db.execute(alter_query, commit=True)
            except Exception as e:
                self._logger.info("Unexpected error: {}", e)
                self.issues = True
