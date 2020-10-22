from ._patch_base import PatchBase
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.patcher)


class Patch(PatchBase):
    name = 'Remove raid hatch delay setting'
    descr = 'Removes the OCR-days raid hatch delay from the settings'

    def _execute(self):
        if self._schema_updater.check_column_exists('settings_devicepool', 'delay_after_hatch'):
            sql = "ALTER TABLE settings_devicepool\n" \
                  "DROP COLUMN delay_after_hatch;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
        if self._schema_updater.check_column_exists('settings_device', 'delay_after_hatch'):
            sql = "ALTER TABLE settings_device\n" \
                  "DROP COLUMN delay_after_hatch;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
