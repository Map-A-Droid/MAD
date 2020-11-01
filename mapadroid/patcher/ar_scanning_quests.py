from ._patch_base import PatchBase
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.patcher)


class Patch(PatchBase):
    name = 'Update tables for AR scanning'
    descr = 'Update trs_quest to be compliant with new scanning requirements'

    def _execute(self):
        sql = """CREATE TABLE IF NOT EXISTS `trs_quest_layers` (
                    `layer` int(11) NOT NULL,
                    `descr` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"""
        self._db.execute(sql, commit=True, suppress_log=True)
        layers = [
            {
                'layer': 1,
                'descr': "Standard quests",
            },
            {
                'layer': 2,
                'descr': "AR Scanning quests",
            },
        ]
        for layer in layers:
            self._db.autoexec_insert("trs_quest_layers", layer, suppress_log=True)
        if not self._schema_updater.check_column_exists('trs_quest', 'pokestop_id'):
            sql = "ALTER TABLE `trs_quest` DROP INDEX IF EXISTS `PRIMARY`"
            self._db.execute(sql, commit=True, raise_exc=True)
            sql = "ALTER TABLE `trs_quest`\n"\
                  "CHANGE `GUID` `pokestop_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL;"
            self._db.execute(sql, commit=True, raise_exc=True)
        if not self._schema_updater.check_column_exists('trs_quest', 'layer'):
            sql = "ALTER TABLE `trs_quest`\n" \
                  " ADD `layer` int(11) NOT NULL DEFAULT 1\n" \
                  " AFTER `pokestop_id`;"
            self._db.execute(sql, commit=True, raise_exc=True)
        sql = "ALTER TABLE `trs_quest` ADD PRIMARY KEY (`pokestop_id`, `layer`);"
        self._db.execute(sql, commit=True, raise_exc=True)
