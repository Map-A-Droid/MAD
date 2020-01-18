from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'MADmin APK Wizard'

    def _execute(self):
        query = (
            "CREATE TABLE IF NOT EXISTS `filestore_meta` ( "
            "`filestore_id` INT NOT NULL AUTO_INCREMENT, "
            "`filename` VARCHAR(255) NOT NULL, "
            "`size` INT NOT NULL, "
            "`mimetype` VARCHAR(255) NOT NULL, "
            "PRIMARY KEY (`filestore_id`))"
        )
        try:
            self._db.execute(query, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
        sql = """CREATE TABLE IF NOT EXISTS `mad_apks` (
            `filestore_id` INT NOT NULL AUTO_INCREMENT,
            `usage` INT NOT NULL,
            `arch` INT NOT NULL,
            `version` VARCHAR(32) NOT NULL,
            PRIMARY KEY (`filestore_id`),
            UNIQUE (`usage`, `arch`),
            CONSTRAINT `fk_fs_apks`
                FOREIGN KEY (`filestore_id`)
                REFERENCES `filestore_meta` (`filestore_id`)
                ON DELETE CASCADE
            )"""
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
        sql = """CREATE TABLE IF NOT EXISTS `filestore_chunks` (
            `chunk_id` INT NOT NULL AUTO_INCREMENT,
            `filestore_id` INT NOT NULL,
            `size` INT NOT NULL,
            `data` LONGBLOB,
            PRIMARY KEY (`chunk_id`),
            UNIQUE (`chunk_id`, `filestore_id`),
            CONSTRAINT `fk_fs_chunks`
                FOREIGN KEY (`filestore_id`)
                REFERENCES `filestore_meta` (`filestore_id`)
                ON DELETE CASCADE
            )"""
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
        sql = """CREATE TABLE IF NOT EXISTS `mad_apk_autosearch` (
            `usage` INT NOT NULL,
            `arch` INT NOT NULL,
            `version` VARCHAR(32) NULL,
            `url` VARCHAR(256) NULL,
            `download_status` TINYINT(1) NOT NULL DEFAULT 0,
            `last_checked` DATETIME NOT NULL,
            PRIMARY KEY (`usage`, `arch`)
            )"""
        try:
            self._db.execute(sql, commit=True)
        except Exception as e:
            self._logger.exception("Unexpected error: {}", e)
            self.issues = True
