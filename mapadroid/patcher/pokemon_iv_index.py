from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add pokemon_iv index'

    def _execute(self):
        add_new_index = (
            "ALTER TABLE pokemon "
            "ADD INDEX pokemon_iv (individual_attack, individual_defense, individual_stamina)"
        )
        drop_old_index = (
            "ALTER TABLE pokemon "
            "DROP INDEX pokemon_individual_attack"
        )

        try:
            if not self._schema_updater.check_index_exists('pokemon', 'pokemon_iv'):
                self._db.execute(add_new_index, commit=True)
            if self._schema_updater.check_index_exists('pokemon', 'pokemon_individual_attack'):
                self._db.execute(drop_old_index, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
