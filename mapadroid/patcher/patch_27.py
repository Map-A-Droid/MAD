from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 27 - trs_spawn performance improvement'

    def _execute(self):
        # Previous versions of this table have an unneeded second index on the spawnpoint field
        sql = "ALTER TABLE `trs_spawn` "\
              "DROP KEY `spawnpoint`, "\
              "DROP KEY `spawnpoint_2`, "\
              "ADD PRIMARY KEY (`spawnpoint`)"
        try:
            self._db.execute(sql, commit=True, suppress_log=True)
        except Exception:
            self._logger.warning("Can't drop and re-create trs_spawn.spawnpoint primary key")

        # trs_spawn.spawnpoint has a different type than pokemon.spawnpoint_id. This
        # spoils the join performance.
        sql = "ALTER TABLE `trs_spawn` "\
              "CHANGE `spawnpoint` `spawnpoint` bigint(20) unsigned NOT NULL"
        try:
            self._db.execute(sql, commit=True, suppress_log=True)
        except Exception:
            pass

        # This index will improve performance on route calculations and map queries
        sql = "ALTER TABLE `trs_spawn` "\
              "ADD KEY `event_lat_long` (`eventid`, `latitude`, `longitude`)"
        try:
            self._db.execute(sql, commit=True, suppress_log=True)
        except Exception:
            self._logger.warning("Can't add additional indices")
