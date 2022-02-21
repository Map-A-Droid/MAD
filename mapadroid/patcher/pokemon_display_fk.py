from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add foreign key for pokemon_display encounter_id'

    def _execute(self):
        # Adding column quest_title for trs_quest
        if not self._schema_updater.check_column_exists('trs_quest', 'quest_title'):
            try:
                # make sure no lines are left in pokemon_display that are no longer in pokemon table
                self._db.execute((
                    "DELETE pd FROM pokemon_display pd"
                    " LEFT JOIN pokemon ON pd.encounter_id=pokemon.encounter_id"
                    " WHERE pokemon.pokemon_id IS NULL"
                ), commit=True)
                self._db.execute((
                    "ALTER TABLE pokemon_display "
                    "ADD CONSTRAINT pokemon_encounter_id_fk FOREIGN KEY (`encounter_id`) "
                    "REFERENCES `pokemon` (`encounter_id`) "
                    "ON UPDATE CASCADE ON DELETE CASCADE"
                ), commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True
