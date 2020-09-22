import json
import os
from ._patch_base import PatchBase
from mapadroid.utils.logging import get_logger, LoggerEnums
from mysql.connector.errors import IntegrityError


logger = get_logger(LoggerEnums.patcher)


class Patch(PatchBase):
    name = 'Move PTC Accounts'
    descr = 'Move PTC accounts from device to pogoauth'

    def _execute(self):
        # Backup the tables
        # Assume that the user has not been given GRANT FILE permissions so just do a manual export
        if self._schema_updater.check_column_exists('settings_device', 'ptc_login'):
            sql = "SELECT `device_id`, `ptc_login`\n"\
                  "FROM `settings_device`\n"\
                  "WHERE `ptc_login` IS NOT NULL"
            with open(os.path.join(self._application_args.temp_path, 'ptc_backup.json'), 'w+') as fh:
                json.dump(self._db.autofetch_all(sql), fh)
        # Add the device link
        if not self._schema_updater.check_column_exists('settings_pogoauth', 'device_id'):
            sql = "ALTER TABLE `settings_pogoauth`\n" \
                  "     ADD `device_id` int(10) unsigned NULL\n" \
                  "     AFTER `account_id`;"
            self._db.execute(sql, raise_exc=True, suppress_log=True, commit=True)
            sql = "ALTER TABLE `settings_pogoauth`\n"\
                  "     ADD CONSTRAINT `fk_spa_device_id`\n"\
                  "     FOREIGN KEY (`device_id`)\n"\
                  "           REFERENCES `settings_device` (`device_id`)\n"\
                  "           ON DELETE CASCADE"
            self._db.execute(sql, raise_exc=True, suppress_log=True, commit=True)
        # Move PTC
        if self._schema_updater.check_column_exists('settings_device', 'ptc_login'):
            sql = "SELECT `device_id`, `ptc_login`, `instance_id`\n"\
                  "FROM `settings_device`\n"\
                  "WHERE `ptc_login` IS NOT NULL"
            ptc_logins = self._db.autofetch_all(sql)
            if ptc_logins:
                for logins in ptc_logins:
                    device_id = logins['device_id']
                    for login in logins['ptc_login'].split("|"):
                        try:
                            username, password = login.split(',', 1)
                        except ValueError:
                            logger.critical('Invalid format for {}', login)
                            continue
                        auth_data = {
                            'username': username,
                            'password': password,
                            'device_id': device_id,
                            'login_type': 'ptc',
                            'instance_id': logins['instance_id']
                        }
                        try:
                            self._db.autoexec_insert('settings_pogoauth', auth_data)
                        except IntegrityError:
                            pass
        # Move Google / Incorrectly assigned PTC
        if self._schema_updater.check_column_exists('settings_device', 'account_id'):
            sql = "SELECT `device_id`, `account_id`\n" \
                  "FROM `settings_device`\n" \
                  "WHERE `account_id` IS NOT NULL"
            google_links = self._db.autofetch_all(sql)
            if google_links:
                for link in google_links:
                    link_data = {
                        'device_id': link['device_id'],
                        'account_id': link['account_id']
                    }
                    where = {
                        'account_id': link['account_id']
                    }
                    try:
                        self._db.autoexec_update('settings_pogoauth', link_data, where_keyvals=where)
                    except IntegrityError:
                        pass
        # Cleanup tables
        if self._schema_updater.check_column_exists('settings_device', 'ptc_login'):
            sql = "ALTER TABLE settings_device\n" \
                  "DROP COLUMN ptc_login;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
        if self._schema_updater.check_column_exists('settings_device', 'account_id'):
            sql = "ALTER TABLE settings_device\n"\
                  " DROP FOREIGN KEY settings_device_ibfk_3"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
            sql = "ALTER TABLE settings_device\n" \
                  "DROP COLUMN account_id;"
            self._db.execute(sql, raise_exc=False, suppress_log=True)
