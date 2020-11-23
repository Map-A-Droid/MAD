COLUMNS = [
    {
        "table": "settings_devicepool",
        "column": "screendetection",
        "ctype": "tinyint(1) DEFAULT NULL"
    },
    {
        "table": "settings_routecalc",
        "column": "recalc_status",
        "ctype": "tinyint(1) DEFAULT 0 AFTER `instance_id`"
    },
    {
        "table": "settings_routecalc",
        "column": "last_updated",
        "ctype": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER `recalc_status`;"
    },
    {
        "table": "settings_area_mon_mitm",
        "column": "max_clustering",
        "ctype": "int DEFAULT NULL"
    },
]
TABLES = [
    """CREATE TABLE IF NOT EXISTS `madmin_instance` (
        `instance_id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `name` VARCHAR(128) NOT NULL,
        PRIMARY KEY (`instance_id`),
        UNIQUE KEY (`name`)
    ) ENGINE = InnoDB;""",

    """CREATE TABLE IF NOT EXISTS `settings_monivlist` (
        `monlist_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) NOT NULL,
        PRIMARY KEY (`monlist_id`),
        -- UNIQUE KEY (`name`, `instance_id`),
        CONSTRAINT `fk_mil_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_monivlist_to_mon` (
        `monlist_id` int UNSIGNED NOT NULL,
        `mon_id` int(11) NOT NULL,
        `mon_order` int(11) NOT NULL,
        PRIMARY KEY (`monlist_id`,`mon_id`),
        INDEX (`monlist_id`),
        INDEX (`mon_id`),
        CONSTRAINT `settings_monivlist_to_mon_ibfk_1`
            FOREIGN KEY (`monlist_id`)
            REFERENCES `settings_monivlist` (`monlist_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_auth` (
        `auth_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `username` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
        `password` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
        PRIMARY KEY (`auth_id`),
        -- UNIQUE (`instance_id`, `username`, `password`),
        CONSTRAINT `fk_sauth_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_devicepool` (
        `pool_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        `post_walk_delay` float DEFAULT NULL,
        `post_teleport_delay` float DEFAULT NULL,
        `walk_after_teleport_distance` float DEFAULT NULL,
        `cool_down_sleep` tinyint(1) DEFAULT NULL,
        `post_turn_screen_on_delay` float DEFAULT NULL,
        `post_pogo_start_delay` float DEFAULT NULL,
        `restart_pogo` int(11) DEFAULT NULL,
        `inventory_clear_rounds` int(11) DEFAULT NULL,
        `inventory_clear_item_amount_tap_duration` int(11) DEFAULT NULL,
        `mitm_wait_timeout` float DEFAULT NULL,
        `vps_delay` float DEFAULT NULL,
        `reboot` tinyint(1) DEFAULT NULL,
        `reboot_thresh` int(11) DEFAULT NULL,
        `restart_thresh` int(11) DEFAULT NULL,
        `post_screenshot_delay` float DEFAULT NULL,
        `screenshot_x_offset` int(11) DEFAULT NULL,
        `screenshot_y_offset` int(11) DEFAULT NULL,
        `screenshot_type` enum('jpeg','png') COLLATE utf8mb4_unicode_ci NULL,
        `screenshot_quality` int(11) DEFAULT NULL,
        `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `injection_thresh_reboot` int(11) DEFAULT NULL,
        PRIMARY KEY (`pool_id`),
        -- UNIQUE KEY (`instance_id`, `name`),
        CONSTRAINT `fk_sds_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_geofence` (
        `geofence_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        `fence_type` enum('polygon','geojson') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'polygon',
        `fence_data` MEDIUMTEXT NOT NULL,
        PRIMARY KEY (`geofence_id`),
        UNIQUE KEY (`name`, `instance_id`)
    ) ENGINE = InnoDB;""",

    """CREATE TABLE IF NOT EXISTS `settings_routecalc` (
        `routecalc_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `routefile` MEDIUMTEXT NULL,
        PRIMARY KEY (`routecalc_id`)
    ) ENGINE = InnoDB;""",

    """CREATE TABLE IF NOT EXISTS `settings_area` (
        `area_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        `mode` enum('idle','iv_mitm','mon_mitm','pokestops','raids_mitm') COLLATE utf8mb4_unicode_ci NOT NULL,
        PRIMARY KEY (`area_id`),
        -- UNIQUE KEY (`instance_id`, `name`),
        CONSTRAINT `fk_sa_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB;""",

    """CREATE TABLE IF NOT EXISTS `settings_area_idle` (
        `area_id` int UNSIGNED NOT NULL,
        `geofence_included` int UNSIGNED NOT NULL,
        `routecalc` int UNSIGNED NOT NULL,
        PRIMARY KEY (`area_id`),
        CONSTRAINT `fk_area_idle`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
            ON DELETE CASCADE,
        CONSTRAINT `fk_area_idle_geofence`
            FOREIGN KEY (`geofence_included`)
            REFERENCES `settings_geofence` (`geofence_id`),
        CONSTRAINT `fk_area_idle_routecalc`
            FOREIGN KEY (`routecalc`)
            REFERENCES `settings_routecalc` (`routecalc_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_area_iv_mitm` (
        `area_id` int UNSIGNED NOT NULL,
        `geofence_included` int UNSIGNED NOT NULL,
        `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `routecalc` int UNSIGNED NOT NULL,
        `speed` float DEFAULT NULL,
        `max_distance` float DEFAULT NULL,
        `delay_after_prio_event` int(11) DEFAULT NULL,
        `priority_queue_clustering_timedelta` float DEFAULT NULL,
        `remove_from_queue_backlog` boolean DEFAULT NULL,
        `starve_route` boolean DEFAULT NULL,
        `monlist_id` int UNSIGNED DEFAULT NULL,
        `min_time_left_seconds` int(11) DEFAULT NULL,
        PRIMARY KEY (`area_id`),
        CONSTRAINT `fk_area_iv_mitm`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
            ON DELETE CASCADE,
        CONSTRAINT `fk_ai_monid`
            FOREIGN KEY (`monlist_id`)
            REFERENCES `settings_monivlist` (`monlist_id`),
        CONSTRAINT `fk_area_iv_mitm_geofence`
            FOREIGN KEY (`geofence_included`)
            REFERENCES `settings_geofence` (`geofence_id`),
        CONSTRAINT `fk_area_iv_mitm_routecalc`
            FOREIGN KEY (`routecalc`)
            REFERENCES `settings_routecalc` (`routecalc_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_area_mon_mitm` (
        `area_id` int UNSIGNED NOT NULL,
        `init` boolean NOT NULL,
        `geofence_included` int UNSIGNED NOT NULL,
        `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `routecalc` int UNSIGNED NOT NULL,
        `coords_spawns_known` boolean NULL,
        `speed` float DEFAULT NULL,
        `max_distance` float DEFAULT NULL,
        `delay_after_prio_event` int DEFAULT NULL,
        `priority_queue_clustering_timedelta` float DEFAULT NULL,
        `remove_from_queue_backlog` float DEFAULT NULL,
        `starve_route` boolean DEFAULT NULL,
        `init_mode_rounds` int DEFAULT NULL,
        `monlist_id` int UNSIGNED DEFAULT NULL,
        `min_time_left_seconds` int DEFAULT NULL,
        PRIMARY KEY (`area_id`),
        CONSTRAINT `fk_area_mon_mitm`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
            ON DELETE CASCADE,
        CONSTRAINT `fk_am_monid`
            FOREIGN KEY (`monlist_id`)
            REFERENCES `settings_monivlist` (`monlist_id`),
        CONSTRAINT `fk_area_mon_mitm_geofence`
            FOREIGN KEY (`geofence_included`)
            REFERENCES `settings_geofence` (`geofence_id`),
        CONSTRAINT `fk_area_mon_mitm_routecalc`
            FOREIGN KEY (`routecalc`)
            REFERENCES `settings_routecalc` (`routecalc_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_area_pokestops` (
        `area_id` int UNSIGNED NOT NULL,
        `geofence_included` int UNSIGNED NOT NULL,
        `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `routecalc` int UNSIGNED NOT NULL,
        `init` boolean NOT NULL,
        `level` boolean NULL,
        `route_calc_algorithm` enum('route') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `speed` float DEFAULT NULL,
        `max_distance` float DEFAULT NULL,
        `ignore_spinned_stops` boolean DEFAULT NULL,
        `cleanup_every_spin` boolean DEFAULT NULL,
        PRIMARY KEY (`area_id`),
        CONSTRAINT `fk_area_pokestops`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
            ON DELETE CASCADE,
        CONSTRAINT `fk_area_pokestops_geofence`
            FOREIGN KEY (`geofence_included`)
            REFERENCES `settings_geofence` (`geofence_id`),
        CONSTRAINT `fk_area_pokestops_routecalc`
            FOREIGN KEY (`routecalc`)
            REFERENCES `settings_routecalc` (`routecalc_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_area_raids_mitm` (
        `area_id` int UNSIGNED NOT NULL,
        `init` boolean NOT NULL,
        `geofence_included` int UNSIGNED NOT NULL,
        `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `routecalc` int UNSIGNED NOT NULL,
        `including_stops` boolean NULL,
        `speed` float DEFAULT NULL,
        `max_distance` float DEFAULT NULL,
        `delay_after_prio_event` int  DEFAULT NULL,
        `priority_queue_clustering_timedelta` float DEFAULT NULL,
        `remove_from_queue_backlog` float DEFAULT NULL,
        `starve_route` boolean DEFAULT NULL,
        `init_mode_rounds` int  DEFAULT NULL,
        `monlist_id` int UNSIGNED DEFAULT NULL,
        PRIMARY KEY (`area_id`),
        CONSTRAINT `fk_area_raids_mitm`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
            ON DELETE CASCADE,
        CONSTRAINT `fk_ar_monid`
            FOREIGN KEY (`monlist_id`)
            REFERENCES `settings_monivlist` (`monlist_id`),
        CONSTRAINT `fk_area_raids_mitm_geofence`
            FOREIGN KEY (`geofence_included`)
            REFERENCES `settings_geofence` (`geofence_id`),
        CONSTRAINT `fk_area_raids_mitm_routecalc`
            FOREIGN KEY (`routecalc`)
            REFERENCES `settings_routecalc` (`routecalc_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_walker` (
        `walker_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        PRIMARY KEY (`walker_id`),
        -- UNIQUE KEY `origin` (`name`, `instance_id`),
        CONSTRAINT `fk_w_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_walkerarea` (
        `walkerarea_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `area_id` int UNSIGNED NOT NULL,
        `algo_type` enum('countdown','timer','round','period','coords', 'idle') COLLATE utf8mb4_unicode_ci NOT NULL,
        `algo_value` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `max_walkers` int  DEFAULT NULL,
        `eventid` int DEFAULT NULL,
        PRIMARY KEY (`walkerarea_id`),
        CONSTRAINT `fk_wa_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE,
        CONSTRAINT `settings_walkerarea_ibfk_1`
            FOREIGN KEY (`area_id`)
            REFERENCES `settings_area` (`area_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_walker_to_walkerarea` (
        `walker_id` int UNSIGNED NOT NULL,
        `walkerarea_id` int UNSIGNED NOT NULL,
        `area_order` int NOT NULL,
        PRIMARY KEY (`walker_id`,`walkerarea_id`, `area_order`),
        INDEX (`walker_id`),
        INDEX (`walkerarea_id`),
        CONSTRAINT `settings_walker_to_walkerarea_ibfk_1`
            FOREIGN KEY (`walker_id`)
            REFERENCES `settings_walker` (`walker_id`)
            ON DELETE CASCADE,
        CONSTRAINT `settings_walker_to_walkerarea_ibfk_2`
            FOREIGN KEY (`walkerarea_id`)
            REFERENCES `settings_walkerarea` (`walkerarea_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    """CREATE TABLE IF NOT EXISTS `settings_device` (
        `device_id` int UNSIGNED NOT NULL AUTO_INCREMENT,
        `guid` varchar(32) NULL,
        `instance_id` int UNSIGNED NOT NULL,
        `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
        `walker_id` int UNSIGNED NOT NULL,
        `pool_id` int UNSIGNED DEFAULT NULL,
        `adbname` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `post_walk_delay` float DEFAULT NULL,
        `post_teleport_delay` float DEFAULT NULL,
        `walk_after_teleport_distance` float DEFAULT NULL,
        `cool_down_sleep` tinyint(1) DEFAULT NULL,
        `post_turn_screen_on_delay` float DEFAULT NULL,
        `post_pogo_start_delay` float DEFAULT NULL,
        `restart_pogo` int DEFAULT NULL,
        `inventory_clear_rounds` int  DEFAULT NULL,
        `inventory_clear_item_amount_tap_duration` int DEFAULT NULL,
        `mitm_wait_timeout` float DEFAULT NULL,
        `vps_delay` float DEFAULT NULL,
        `reboot` tinyint(1) DEFAULT NULL,
        `reboot_thresh` int DEFAULT NULL,
        `restart_thresh` int DEFAULT NULL,
        `post_screenshot_delay` float DEFAULT NULL,
        `screenshot_x_offset` int DEFAULT NULL,
        `screenshot_y_offset` int DEFAULT NULL,
        `screenshot_type` enum('jpeg','png') COLLATE utf8mb4_unicode_ci NULL,
        `screenshot_quality` int DEFAULT NULL,
        `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `screendetection` tinyint(1) DEFAULT NULL,
        `logintype` enum('google','ptc') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `ggl_login_mail` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `ptc_login` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        `clear_game_data` tinyint(1) DEFAULT NULL,
        `account_rotation` tinyint(1) DEFAULT NULL,
        `rotation_waittime` float DEFAULT NULL,
        `rotate_on_lvl_30` tinyint(1) DEFAULT NULL,
        `injection_thresh_reboot` int DEFAULT NULL,
        PRIMARY KEY (`device_id`),
        -- UNIQUE KEY (`name`, `instance_id`),
        -- UNIQUE KEY (`adbname`, `instance_id`),
        CONSTRAINT `settings_device_ibfk_1`
            FOREIGN KEY (`walker_id`)
            REFERENCES `settings_walker` (`walker_id`),
        CONSTRAINT `settings_device_ibfk_2`
            FOREIGN KEY (`pool_id`)
            REFERENCES `settings_devicepool` (`pool_id`),
        CONSTRAINT `fk_sd_instance`
            FOREIGN KEY (`instance_id`)
            REFERENCES `madmin_instance` (`instance_id`)
            ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
]
