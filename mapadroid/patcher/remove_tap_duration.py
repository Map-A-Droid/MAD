from mapadroid.utils.logging import LoggerEnums, get_logger

from ._patch_base import PatchBase

logger = get_logger(LoggerEnums.patcher)


class Patch(PatchBase):
    name = 'Remove inventory_clear_item_amount_tap_duration'
    descr = 'Removes the setting defining how long the + button would be held during item deletion'

    def _execute(self):
        if self._schema_updater.check_column_exists('settings_devicepool', 'inventory_clear_item_amount_tap_duration'):
            sql = "ALTER TABLE settings_devicepool\n" \
                  "DROP COLUMN inventory_clear_item_amount_tap_duration;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
        if self._schema_updater.check_column_exists('settings_device', 'inventory_clear_item_amount_tap_duration'):
            sql = "ALTER TABLE settings_device\n" \
                  "DROP COLUMN inventory_clear_item_amount_tap_duration;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
