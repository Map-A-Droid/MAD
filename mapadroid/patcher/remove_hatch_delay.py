from mapadroid.utils.logging import LoggerEnums, get_logger

from ._patch_base import PatchBase

logger = get_logger(LoggerEnums.patcher)


class Patch(PatchBase):
    name = 'Remove raid hatch delay setting'
    descr = 'Removes the OCR-days raid hatch delay from the settings'

    def _execute(self):
        if self._schema_updater.check_column_exists('settings_devicepool', 'delay_after_hatch'):
            sql = "ALTER TABLE settings_devicepool\n" \
                  "DROP COLUMN delay_after_hatch;"
            await self._run_raw_sql_query(sql)
        if self._schema_updater.check_column_exists('settings_device', 'delay_after_hatch'):
            sql = "ALTER TABLE settings_device\n" \
                  "DROP COLUMN delay_after_hatch;"
            await self._run_raw_sql_query(sql)
