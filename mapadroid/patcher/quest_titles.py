from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Add quest title column'

    def _execute(self):
        # Adding column quest_title for trs_quest
        if not self._schema_updater.check_column_exists('trs_quest', 'quest_title'):
            query = (
                "ALTER TABLE trs_quest "
                "ADD quest_title varchar(100) COLLATE utf8mb4_unicode_ci  DEFAULT NULL"
            )
            try:
                self._db.execute(query, commit=True)
            except Exception as e:
                self._logger.exception("Unexpected error: {}", e)
                self.issues = True

