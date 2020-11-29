from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Extend trs_quest.quest_reward length'
    descr = 'New Protos, more data.'

    def _execute(self):
        alter_sql = """
            ALTER TABLE `trs_quest`
            MODIFY COLUMN `quest_reward` varchar(2560)
            COLLATE utf8mb4_unicode_ci DEFAULT NULL;
        """
        try:
            self._db.execute(alter_sql, commit=True, raise_exec=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
