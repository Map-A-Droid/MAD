from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add foreign key for pokemon_display encounter_id'

    def _execute(self):
        # Adding column quest_title for trs_quest
        if not self._schema_updater.check_column_exists('trs_quest', 'quest_title'):
            query = (
                "ALTER TABLE pokemon_display "
                "ADD CONSTRAINT pokemon_encounter_id_fk FOREIGN KEY (`encounter_id`) "
                "REFERENCES `pokemon` (`encounter_id`) "
                "ON UPDATE CASCADE ON DELETE CASCADE"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
