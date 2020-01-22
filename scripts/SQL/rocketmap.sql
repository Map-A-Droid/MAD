SET FOREIGN_KEY_CHECKS=0;
SET NAMES utf8mb4;

CREATE TABLE `filestore_chunks` (
    `chunk_id` int(11) NOT NULL AUTO_INCREMENT,
    `filestore_id` int(11) NOT NULL,
    `size` int(11) NOT NULL,
    `data` longblob,
    PRIMARY KEY (`chunk_id`),
    UNIQUE KEY `chunk_id` (`chunk_id`,`filestore_id`),
    KEY `fk_fs_chunks` (`filestore_id`),
    CONSTRAINT `fk_fs_chunks` FOREIGN KEY (`filestore_id`)
        REFERENCES `filestore_meta` (`filestore_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `filestore_meta` (
    `filestore_id` int(11) NOT NULL AUTO_INCREMENT,
    `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    `size` int(11) NOT NULL,
    `mimetype` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`filestore_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gomap` (
    `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gym` (
    `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `team_id` smallint(6) NOT NULL DEFAULT '0',
    `guard_pokemon_id` smallint(6) NOT NULL DEFAULT '0',
    `slots_available` smallint(6) NOT NULL DEFAULT '6',
    `enabled` tinyint(1) NOT NULL DEFAULT '1',
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `total_cp` smallint(6) NOT NULL DEFAULT '0',
    `is_in_battle` tinyint(1) NOT NULL DEFAULT '0',
    `gender` smallint(6) DEFAULT NULL,
    `form` smallint(6) DEFAULT NULL,
    `costume` smallint(6) DEFAULT NULL,
    `weather_boosted_condition` smallint(6) DEFAULT NULL,
    `shiny` tinyint(1) DEFAULT NULL,
    `last_modified` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `last_scanned` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `is_ex_raid_eligible` tinyint(1) NOT NULL DEFAULT '0',
    PRIMARY KEY (`gym_id`),
    KEY `gym_last_modified` (`last_modified`),
    KEY `gym_last_scanned` (`last_scanned`),
    KEY `gym_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gymdetails` (
    `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `description` longtext COLLATE utf8mb4_unicode_ci,
    `url` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_scanned` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`gym_id`),
    CONSTRAINT `fk_gd_gym_id` FOREIGN KEY (`gym_id`)
        REFERENCES `gym` (`gym_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gymmember` (
    `gym_id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `pokemon_uid` bigint(20) unsigned NOT NULL,
    `last_scanned` datetime NOT NULL,
    `deployment_time` datetime NOT NULL,
    `cp_decayed` smallint(6) NOT NULL,
    KEY `gymmember_gym_id` (`gym_id`),
    KEY `gymmember_pokemon_uid` (`pokemon_uid`),
    KEY `gymmember_last_scanned` (`last_scanned`),
    PRIMARY KEY (`gym_id`),
    CONSTRAINT `fk_gm_gym_id` FOREIGN KEY (`gym_id`)
        REFERENCES `gym` (`gym_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `gympokemon` (
    `pokemon_uid` bigint(20) unsigned NOT NULL,
    `pokemon_id` smallint(6) NOT NULL,
    `cp` smallint(6) NOT NULL,
    `trainer_name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `num_upgrades` smallint(6) DEFAULT NULL,
    `move_1` smallint(6) DEFAULT NULL,
    `move_2` smallint(6) DEFAULT NULL,
    `height` float DEFAULT NULL,
    `weight` float DEFAULT NULL,
    `stamina` smallint(6) DEFAULT NULL,
    `stamina_max` smallint(6) DEFAULT NULL,
    `cp_multiplier` float DEFAULT NULL,
    `additional_cp_multiplier` float DEFAULT NULL,
    `iv_defense` smallint(6) DEFAULT NULL,
    `iv_stamina` smallint(6) DEFAULT NULL,
    `iv_attack` smallint(6) DEFAULT NULL,
    `gender` smallint(6) DEFAULT NULL,
    `form` smallint(6) DEFAULT NULL,
    `costume` smallint(6) DEFAULT NULL,
    `weather_boosted_condition` smallint(6) DEFAULT NULL,
    `shiny` tinyint(1) DEFAULT NULL,
    `last_seen` datetime NOT NULL,
    PRIMARY KEY (`pokemon_uid`),
    KEY `gympokemon_trainer_name` (`trainer_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `hashkeys` (
    `key` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
    `maximum` smallint(6) NOT NULL,
    `remaining` smallint(6) NOT NULL,
    `peak` smallint(6) NOT NULL,
    `expires` datetime DEFAULT NULL,
    `last_updated` datetime NOT NULL,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `locationaltitude` (
    `cellid` bigint(20) unsigned NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `last_modified` datetime DEFAULT NULL,
    `altitude` double NOT NULL,
    PRIMARY KEY (`cellid`),
    KEY `locationaltitude_last_modified` (`last_modified`),
    KEY `locationaltitude_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `mad_apk_autosearch` (
    `usage` int(11) NOT NULL,
    `arch` int(11) NOT NULL,
    `version` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `url` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `download_status` tinyint(1) NOT NULL DEFAULT '0',
    `last_checked` datetime NOT NULL,
    PRIMARY KEY (`usage`,`arch`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `mad_apks` (
    `filestore_id` int(11) NOT NULL AUTO_INCREMENT,
    `usage` int(11) NOT NULL,
    `arch` int(11) NOT NULL,
    `version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`filestore_id`),
    UNIQUE KEY `usage` (`usage`,`arch`),
    CONSTRAINT `fk_fs_apks` FOREIGN KEY (`filestore_id`)
        REFERENCES `filestore_meta` (`filestore_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `madmin_instance` (
    `instance_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`instance_id`),
    UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `mainworker` (
    `worker_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `message` longtext COLLATE utf8mb4_unicode_ci,
    `method` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_modified` datetime NOT NULL,
    `accounts_working` int(11) NOT NULL,
    `accounts_captcha` int(11) NOT NULL,
    `accounts_failed` int(11) NOT NULL,
    `success` int(11) NOT NULL,
    `fail` int(11) NOT NULL,
    `empty` int(11) NOT NULL,
    `skip` int(11) NOT NULL,
    `captcha` int(11) NOT NULL,
    `start` int(11) NOT NULL,
    `elapsed` int(11) NOT NULL,
    PRIMARY KEY (`worker_name`),
    KEY `mainworker_last_modified` (`last_modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `playerlocale` (
    `location` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `country` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
    `language` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
    `timezone` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
PRIMARY KEY (`location`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `pokemon` (
    `encounter_id` bigint(20) unsigned NOT NULL,
    `spawnpoint_id` bigint(20) unsigned NOT NULL,
    `pokemon_id` smallint(6) NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `disappear_time` datetime NOT NULL,
    `individual_attack` smallint(6) DEFAULT NULL,
    `individual_defense` smallint(6) DEFAULT NULL,
    `individual_stamina` smallint(6) DEFAULT NULL,
    `move_1` smallint(6) DEFAULT NULL,
    `move_2` smallint(6) DEFAULT NULL,
    `cp` smallint(6) DEFAULT NULL,
    `cp_multiplier` float DEFAULT NULL,
    `weight` float DEFAULT NULL,
    `height` float DEFAULT NULL,
    `gender` smallint(6) DEFAULT NULL,
    `form` smallint(6) DEFAULT NULL,
    `costume` smallint(6) DEFAULT NULL,
    `catch_prob_1` double DEFAULT NULL,
    `catch_prob_2` double DEFAULT NULL,
    `catch_prob_3` double DEFAULT NULL,
    `rating_attack` varchar(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `rating_defense` varchar(2) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `weather_boosted_condition` smallint(6) DEFAULT NULL,
    `last_modified` datetime DEFAULT NULL,
    PRIMARY KEY (`encounter_id`),
    KEY `pokemon_spawnpoint_id` (`spawnpoint_id`),
    KEY `pokemon_pokemon_id` (`pokemon_id`),
    KEY `pokemon_last_modified` (`last_modified`),
    KEY `pokemon_latitude_longitude` (`latitude`,`longitude`),
    KEY `pokemon_disappear_time_pokemon_id` (`disappear_time`,`pokemon_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `pokestop` (
    `pokestop_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `enabled` tinyint(1) NOT NULL DEFAULT '1',
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `last_modified` datetime DEFAULT CURRENT_TIMESTAMP,
    `lure_expiration` datetime DEFAULT NULL,
    `active_fort_modifier` smallint(6) DEFAULT NULL,
    `last_updated` datetime DEFAULT NULL,
    `name` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `image` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `incident_start` datetime DEFAULT NULL,
    `incident_expiration` datetime DEFAULT NULL,
    `incident_grunt_type` smallint(1) DEFAULT NULL,
    `encounter_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    PRIMARY KEY (`pokestop_id`),
    KEY `pokestop_last_modified` (`last_modified`),
    KEY `pokestop_lure_expiration` (`lure_expiration`),
    KEY `pokestop_active_fort_modifier` (`active_fort_modifier`),
    KEY `pokestop_last_updated` (`last_updated`),
    KEY `pokestop_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `raid` (
    `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `level` int(11) NOT NULL,
    `spawn` datetime NOT NULL,
    `start` datetime NOT NULL,
    `end` datetime NOT NULL,
    `pokemon_id` smallint(6) DEFAULT NULL,
    `cp` int(11) DEFAULT NULL,
    `move_1` smallint(6) DEFAULT NULL,
    `move_2` smallint(6) DEFAULT NULL,
    `last_scanned` datetime NOT NULL,
    `form` smallint(6) DEFAULT NULL,
    `is_exclusive` tinyint(1) DEFAULT NULL,
    `gender` tinyint(1) DEFAULT NULL,
    `costume` tinyint(1) DEFAULT NULL,
    PRIMARY KEY (`gym_id`),
    KEY `raid_level` (`level`),
    KEY `raid_spawn` (`spawn`),
    KEY `raid_start` (`start`),
    KEY `raid_end` (`end`),
    KEY `raid_last_scanned` (`last_scanned`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `scannedlocation` (
    `cellid` bigint(20) unsigned NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `last_modified` datetime DEFAULT NULL,
    `done` tinyint(1) NOT NULL,
    `band1` smallint(6) NOT NULL,
    `band2` smallint(6) NOT NULL,
    `band3` smallint(6) NOT NULL,
    `band4` smallint(6) NOT NULL,
    `band5` smallint(6) NOT NULL,
    `midpoint` smallint(6) NOT NULL,
    `width` smallint(6) NOT NULL,
    PRIMARY KEY (`cellid`),
    KEY `scannedlocation_last_modified` (`last_modified`),
    KEY `scannedlocation_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `scanspawnpoint` (
    `scannedlocation_id` bigint(20) unsigned NOT NULL,
    `spawnpoint_id` bigint(20) unsigned NOT NULL,
    PRIMARY KEY (`spawnpoint_id`,`scannedlocation_id`),
    KEY `scanspawnpoint_scannedlocation_id` (`scannedlocation_id`),
    KEY `scanspawnpoint_spawnpoint_id` (`spawnpoint_id`),
    CONSTRAINT `scanspawnpoint_ibfk_1` FOREIGN KEY (`scannedlocation_id`)
        REFERENCES `scannedlocation` (`cellid`),
    CONSTRAINT `scanspawnpoint_ibfk_2` FOREIGN KEY (`spawnpoint_id`)
        REFERENCES `spawnpoint` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area` (
    `area_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    `mode` enum('idle','iv_mitm','mon_mitm','pokestops','raids_mitm') COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_sa_instance` (`instance_id`),
    CONSTRAINT `fk_sa_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area_idle` (
    `area_id` int(10) unsigned NOT NULL,
    `geofence_included` int(10) unsigned NOT NULL,
    `routecalc` int(10) unsigned NOT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_area_idle_geofence` (`geofence_included`),
    KEY `fk_area_idle_routecalc` (`routecalc`),
    CONSTRAINT `fk_area_idle` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_area_idle_geofence` FOREIGN KEY (`geofence_included`)
        REFERENCES `settings_geofence` (`geofence_id`),
    CONSTRAINT `fk_area_idle_routecalc` FOREIGN KEY (`routecalc`)
        REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area_iv_mitm` (
    `area_id` int(10) unsigned NOT NULL,
    `geofence_included` int(10) unsigned NOT NULL,
    `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `routecalc` int(10) unsigned NOT NULL,
    `speed` float DEFAULT NULL,
    `max_distance` float DEFAULT NULL,
    `delay_after_prio_event` int(11) DEFAULT NULL,
    `priority_queue_clustering_timedelta` float DEFAULT NULL,
    `remove_from_queue_backlog` tinyint(1) DEFAULT NULL,
    `starve_route` tinyint(1) DEFAULT NULL,
    `monlist_id` int(10) unsigned DEFAULT NULL,
    `min_time_left_seconds` int(11) DEFAULT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_ai_monid` (`monlist_id`),
    KEY `fk_area_iv_mitm_geofence` (`geofence_included`),
    KEY `fk_area_iv_mitm_routecalc` (`routecalc`),
    CONSTRAINT `fk_ai_monid` FOREIGN KEY (`monlist_id`)
        REFERENCES `settings_monivlist` (`monlist_id`),
    CONSTRAINT `fk_area_iv_mitm` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_area_iv_mitm_geofence` FOREIGN KEY (`geofence_included`)
        REFERENCES `settings_geofence` (`geofence_id`),
    CONSTRAINT `fk_area_iv_mitm_routecalc` FOREIGN KEY (`routecalc`)
        REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area_mon_mitm` (
    `area_id` int(10) unsigned NOT NULL,
    `init` tinyint(1) NOT NULL,
    `geofence_included` int(10) unsigned NOT NULL,
    `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `routecalc` int(10) unsigned NOT NULL,
    `coords_spawns_known` tinyint(1) NOT NULL,
    `speed` float DEFAULT NULL,
    `max_distance` float DEFAULT NULL,
    `delay_after_prio_event` int(11) DEFAULT NULL,
    `priority_queue_clustering_timedelta` float DEFAULT NULL,
    `remove_from_queue_backlog` float DEFAULT NULL,
    `starve_route` tinyint(1) DEFAULT NULL,
    `init_mode_rounds` int(11) DEFAULT NULL,
    `monlist_id` int(10) unsigned DEFAULT NULL,
    `min_time_left_seconds` int(11) DEFAULT NULL,
    `max_clustering` int(11) DEFAULT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_am_monid` (`monlist_id`),
    KEY `fk_area_mon_mitm_geofence` (`geofence_included`),
    KEY `fk_area_mon_mitm_routecalc` (`routecalc`),
    CONSTRAINT `fk_am_monid` FOREIGN KEY (`monlist_id`)
        REFERENCES `settings_monivlist` (`monlist_id`),
    CONSTRAINT `fk_area_mon_mitm` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_area_mon_mitm_geofence` FOREIGN KEY (`geofence_included`)
        REFERENCES `settings_geofence` (`geofence_id`),
    CONSTRAINT `fk_area_mon_mitm_routecalc` FOREIGN KEY (`routecalc`)
        REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area_pokestops` (
    `area_id` int(10) unsigned NOT NULL,
    `geofence_included` int(10) unsigned NOT NULL,
    `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `routecalc` int(10) unsigned NOT NULL,
    `init` tinyint(1) NOT NULL,
    `level` tinyint(1) DEFAULT NULL,
    `route_calc_algorithm` enum('optimized','quick') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `speed` float DEFAULT NULL,
    `max_distance` float DEFAULT NULL,
    `ignore_spinned_stops` tinyint(1) DEFAULT NULL,
    `cleanup_every_spin` tinyint(1) DEFAULT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_area_pokestops_geofence` (`geofence_included`),
    KEY `fk_area_pokestops_routecalc` (`routecalc`),
    CONSTRAINT `fk_area_pokestops` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_area_pokestops_geofence`
        FOREIGN KEY (`geofence_included`)
        REFERENCES `settings_geofence` (`geofence_id`),
    CONSTRAINT `fk_area_pokestops_routecalc` FOREIGN KEY (`routecalc`)
        REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_area_raids_mitm` (
    `area_id` int(10) unsigned NOT NULL,
    `init` tinyint(1) NOT NULL,
    `geofence_included` int(10) unsigned NOT NULL,
    `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `routecalc` int(10) unsigned NOT NULL,
    `including_stops` tinyint(1) DEFAULT NULL,
    `speed` float DEFAULT NULL,
    `max_distance` float DEFAULT NULL,
    `delay_after_prio_event` int(11) DEFAULT NULL,
    `priority_queue_clustering_timedelta` float DEFAULT NULL,
    `remove_from_queue_backlog` float DEFAULT NULL,
    `starve_route` tinyint(1) DEFAULT NULL,
    `init_mode_rounds` int(11) DEFAULT NULL,
    `monlist_id` int(10) unsigned DEFAULT NULL,
    PRIMARY KEY (`area_id`),
    KEY `fk_ar_monid` (`monlist_id`),
    KEY `fk_area_raids_mitm_geofence` (`geofence_included`),
    KEY `fk_area_raids_mitm_routecalc` (`routecalc`),
    CONSTRAINT `fk_ar_monid` FOREIGN KEY (`monlist_id`)
        REFERENCES `settings_monivlist` (`monlist_id`),
    CONSTRAINT `fk_area_raids_mitm` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_area_raids_mitm_geofence` FOREIGN KEY (`geofence_included`)
        REFERENCES `settings_geofence` (`geofence_id`),
    CONSTRAINT `fk_area_raids_mitm_routecalc` FOREIGN KEY (`routecalc`)
        REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_auth` (
    `auth_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `username` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
    `password` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`auth_id`),
    KEY `fk_sauth_instance` (`instance_id`),
    CONSTRAINT `fk_sauth_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_device` (
    `device_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    `walker_id` int(10) unsigned NOT NULL,
    `pool_id` int(10) unsigned DEFAULT NULL,
    `adbname` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `post_walk_delay` float DEFAULT NULL,
    `post_teleport_delay` float DEFAULT NULL,
    `walk_after_teleport_distance` float DEFAULT NULL,
    `cool_down_sleep` tinyint(1) DEFAULT NULL,
    `post_turn_screen_on_delay` float DEFAULT NULL,
    `post_pogo_start_delay` float DEFAULT NULL,
    `restart_pogo` int(11) DEFAULT NULL,
    `delay_after_hatch` float DEFAULT NULL,
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
    `screenshot_type` enum('jpeg','png') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `screenshot_quality` int(11) DEFAULT NULL,
    `route_calc_algorithm` enum('optimized','quick') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `screendetection` tinyint(1) DEFAULT NULL,
    `logintype` enum('google','ptc') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `ggl_login_mail` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `ptc_login` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `clear_game_data` tinyint(1) DEFAULT NULL,
    `account_rotation` tinyint(1) DEFAULT NULL,
    `rotation_waittime` float DEFAULT NULL,
    `rotate_on_lvl_30` tinyint(1) DEFAULT NULL,
    `injection_thresh_reboot` int(11) DEFAULT NULL,
    PRIMARY KEY (`device_id`),
    KEY `settings_device_ibfk_1` (`walker_id`),
    KEY `settings_device_ibfk_2` (`pool_id`),
    KEY `fk_sd_instance` (`instance_id`),
    CONSTRAINT `fk_sd_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE,
    CONSTRAINT `settings_device_ibfk_1` FOREIGN KEY (`walker_id`)
        REFERENCES `settings_walker` (`walker_id`),
    CONSTRAINT `settings_device_ibfk_2` FOREIGN KEY (`pool_id`)
        REFERENCES `settings_devicepool` (`pool_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_devicepool` (
    `pool_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    `post_walk_delay` float DEFAULT NULL,
    `post_teleport_delay` float DEFAULT NULL,
    `walk_after_teleport_distance` float DEFAULT NULL,
    `cool_down_sleep` tinyint(1) DEFAULT NULL,
    `post_turn_screen_on_delay` float DEFAULT NULL,
    `post_pogo_start_delay` float DEFAULT NULL,
    `restart_pogo` int(11) DEFAULT NULL,
    `delay_after_hatch` float DEFAULT NULL,
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
    `screenshot_type` enum('jpeg','png') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `screenshot_quality` int(11) DEFAULT NULL,
    `route_calc_algorithm` enum('optimized','quick') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `injection_thresh_reboot` int(11) DEFAULT NULL,
    `screendetection` tinyint(1) DEFAULT NULL,
    PRIMARY KEY (`pool_id`),
    KEY `fk_sds_instance` (`instance_id`),
    CONSTRAINT `fk_sds_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_geofence` (
    `geofence_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    `fence_type` enum('polygon','geojson') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'polygon',
    `fence_data` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`geofence_id`),
    UNIQUE KEY `name` (`name`,`instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_monivlist` (
    `monlist_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`monlist_id`),
    KEY `fk_mil_instance` (`instance_id`),
    CONSTRAINT `fk_mil_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_monivlist_to_mon` (
    `monlist_id` int(10) unsigned NOT NULL,
    `mon_id` int(11) NOT NULL,
    `mon_order` int(11) NOT NULL,
    PRIMARY KEY (`monlist_id`,`mon_id`),
    KEY `monlist_id` (`monlist_id`),
    KEY `mon_id` (`mon_id`),
    CONSTRAINT `settings_monivlist_to_mon_ibfk_1` FOREIGN KEY (`monlist_id`)
        REFERENCES `settings_monivlist` (`monlist_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_routecalc` (
    `routecalc_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `recalc_status` tinyint(1) DEFAULT '0',
    `last_updated` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `routefile` mediumtext COLLATE utf8mb4_unicode_ci,
    PRIMARY KEY (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_walker` (
    `walker_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`walker_id`),
    KEY `fk_w_instance` (`instance_id`),
    CONSTRAINT `fk_w_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_walker_to_walkerarea` (
    `walker_id` int(10) unsigned NOT NULL,
    `walkerarea_id` int(10) unsigned NOT NULL,
    `area_order` int(11) NOT NULL,
    PRIMARY KEY (`walker_id`,`walkerarea_id`,`area_order`),
    KEY `walker_id` (`walker_id`),
    KEY `walkerarea_id` (`walkerarea_id`),
    CONSTRAINT `settings_walker_to_walkerarea_ibfk_1` FOREIGN KEY (`walker_id`)
        REFERENCES `settings_walker` (`walker_id`)
        ON DELETE CASCADE,
    CONSTRAINT `settings_walker_to_walkerarea_ibfk_2` FOREIGN KEY (`walkerarea_id`)
        REFERENCES `settings_walkerarea` (`walkerarea_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `settings_walkerarea` (
    `walkerarea_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `instance_id` int(10) unsigned NOT NULL,
    `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `area_id` int(10) unsigned NOT NULL,
    `algo_type` enum('countdown','timer','round','period','coords','idle') COLLATE utf8mb4_unicode_ci NOT NULL,
    `algo_value` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `max_walkers` int(11) DEFAULT NULL,
    PRIMARY KEY (`walkerarea_id`),
    KEY `fk_wa_instance` (`instance_id`),
    KEY `settings_walkerarea_ibfk_1` (`area_id`),
    CONSTRAINT `fk_wa_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE,
    CONSTRAINT `settings_walkerarea_ibfk_1` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `spawnpoint` (
    `id` bigint(20) unsigned NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `last_scanned` datetime NOT NULL,
    `kind` varchar(4) COLLATE utf8mb4_unicode_ci NOT NULL,
    `links` varchar(4) COLLATE utf8mb4_unicode_ci NOT NULL,
    `missed_count` int(11) NOT NULL,
    `latest_seen` smallint(6) NOT NULL,
    `earliest_unseen` smallint(6) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `spawnpoint_last_scanned` (`last_scanned`),
    KEY `spawnpoint_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `spawnpointdetectiondata` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `encounter_id` bigint(20) unsigned NOT NULL,
    `spawnpoint_id` bigint(20) unsigned NOT NULL,
    `scan_time` datetime NOT NULL,
    `tth_secs` smallint(6) DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `spawnpointdetectiondata_spawnpoint_id` (`spawnpoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `token` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `token` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_updated` datetime NOT NULL,
    PRIMARY KEY (`id`),
    KEY `token_last_updated` (`last_updated`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trainer` (
    `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `team` smallint(6) NOT NULL,
    `level` smallint(6) NOT NULL,
    `last_seen` datetime NOT NULL,
    PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_quest` (
    `GUID` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `quest_type` tinyint(3) NOT NULL,
    `quest_timestamp` int(11) NOT NULL,
    `quest_stardust` smallint(4) NOT NULL,
    `quest_pokemon_id` smallint(4) NOT NULL,
    `quest_reward_type` smallint(3) NOT NULL,
    `quest_item_id` smallint(3) NOT NULL,
    `quest_item_amount` tinyint(2) NOT NULL,
    `quest_target` tinyint(3) NOT NULL,
    `quest_condition` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `quest_reward` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `quest_template` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `quest_task` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `quest_pokemon_form_id` smallint(6) NOT NULL DEFAULT '0',
    `quest_pokemon_costume_id` smallint(6) NOT NULL DEFAULT '0',
    PRIMARY KEY (`GUID`),
    KEY `quest_type` (`quest_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_s2cells` (
    `id` bigint(20) unsigned NOT NULL,
    `level` int(11) NOT NULL,
    `center_latitude` double NOT NULL,
    `center_longitude` double NOT NULL,
    `updated` int(11) NOT NULL,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_spawn` (
    `spawnpoint` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `spawndef` int(11) NOT NULL DEFAULT '240',
    `earliest_unseen` int(6) NOT NULL,
    `last_scanned` datetime DEFAULT NULL,
    `first_detection` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `last_non_scanned` datetime DEFAULT NULL,
    `calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    UNIQUE KEY `spawnpoint_2` (`spawnpoint`),
    KEY `spawnpoint` (`spawnpoint`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_spawnsightings` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `encounter_id` bigint(20) unsigned NOT NULL,
    `spawnpoint_id` bigint(20) unsigned NOT NULL,
    `scan_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `tth_secs` int(11) DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `trs_spawnpointdd_spawnpoint_id` (`spawnpoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_stats_detect` (
    `id` int(100) NOT NULL AUTO_INCREMENT,
    `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `timestamp_scan` int(11) NOT NULL,
    `mon` int(255) DEFAULT NULL,
    `raid` int(255) DEFAULT NULL,
    `mon_iv` int(11) DEFAULT NULL,
    `quest` int(100) DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `worker` (`worker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_stats_detect_raw` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `type_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `type` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
    `count` int(11) NOT NULL,
    `is_shiny` tinyint(1) NOT NULL DEFAULT '0',
    `timestamp_scan` int(11) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `worker` (`worker`),
    KEY `typeworker` (`worker`,`type_id`),
    KEY `shiny` (`is_shiny`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_stats_location` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `timestamp_scan` int(11) NOT NULL,
    `location_count` int(11) NOT NULL,
    `location_ok` int(11) NOT NULL,
    `location_nok` int(11) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `worker` (`worker`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_stats_location_raw` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `lat` double NOT NULL,
    `lng` double NOT NULL,
    `fix_ts` int(11) NOT NULL,
    `data_ts` int(11) NOT NULL,
    `type` tinyint(1) NOT NULL,
    `walker` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
    `success` tinyint(1) NOT NULL,
    `period` int(11) NOT NULL,
    `count` int(11) NOT NULL,
    `transporttype` tinyint(1) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `count_same_events` (`worker`,`lat`,`lng`,`type`,`period`),
    KEY `latlng` (`lat`,`lng`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_status` (
    `instance_id` int(10) unsigned NOT NULL,
    `device_id` int(10) unsigned NOT NULL,
    `currentPos` point DEFAULT NULL,
    `lastPos` point DEFAULT NULL,
    `routePos` int(11) DEFAULT NULL,
    `routeMax` int(11) DEFAULT NULL,
    `area_id` int(10) unsigned DEFAULT NULL,
    `idle` tinyint(4) DEFAULT '0',
    `rebootCounter` int(11) DEFAULT NULL,
    `lastProtoDateTime` timestamp NULL DEFAULT NULL,
    `lastPogoRestart` timestamp NULL DEFAULT NULL,
    `init` tinyint(1) DEFAULT NULL,
    `rebootingOption` tinyint(1) DEFAULT NULL,
    `restartCounter` int(11) DEFAULT NULL,
    `lastPogoReboot` timestamp NULL DEFAULT NULL,
    `globalrebootcount` int(11) DEFAULT '0',
    `globalrestartcount` int(11) DEFAULT '0',
    `currentSleepTime` int(11) NOT NULL DEFAULT '0',
    PRIMARY KEY (`device_id`),
    KEY `fk_ts_instance` (`instance_id`),
    KEY `fk_ts_areaid` (`area_id`),
    CONSTRAINT `fk_ts_areaid` FOREIGN KEY (`area_id`)
        REFERENCES `settings_area` (`area_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_ts_dev_id` FOREIGN KEY (`device_id`)
        REFERENCES `settings_device` (`device_id`)
        ON DELETE CASCADE,
    CONSTRAINT `fk_ts_instance` FOREIGN KEY (`instance_id`)
        REFERENCES `madmin_instance` (`instance_id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_usage` (
    `usage_id` int(10) NOT NULL AUTO_INCREMENT,
    `instance` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `cpu` float DEFAULT NULL,
    `memory` float DEFAULT NULL,
    `garbage` int(5) DEFAULT NULL,
    `timestamp` int(11) DEFAULT NULL,
    PRIMARY KEY (`usage_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `trs_visited` (
    `pokestop_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `origin` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`pokestop_id`,`origin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `versions` (
    `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `val` smallint(6) NOT NULL,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `weather` (
    `s2_cell_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `latitude` double NOT NULL,
    `longitude` double NOT NULL,
    `cloud_level` smallint(6) DEFAULT NULL,
    `rain_level` smallint(6) DEFAULT NULL,
    `wind_level` smallint(6) DEFAULT NULL,
    `snow_level` smallint(6) DEFAULT NULL,
    `fog_level` smallint(6) DEFAULT NULL,
    `wind_direction` smallint(6) DEFAULT NULL,
    `gameplay_weather` smallint(6) DEFAULT NULL,
    `severity` smallint(6) DEFAULT NULL,
    `warn_weather` smallint(6) DEFAULT NULL,
    `world_time` smallint(6) DEFAULT NULL,
    `last_updated` datetime DEFAULT NULL,
    PRIMARY KEY (`s2_cell_id`),
    KEY `weather_cloud_level` (`cloud_level`),
    KEY `weather_rain_level` (`rain_level`),
    KEY `weather_wind_level` (`wind_level`),
    KEY `weather_snow_level` (`snow_level`),
    KEY `weather_fog_level` (`fog_level`),
    KEY `weather_wind_direction` (`wind_direction`),
    KEY `weather_gameplay_weather` (`gameplay_weather`),
    KEY `weather_severity` (`severity`),
    KEY `weather_warn_weather` (`warn_weather`),
    KEY `weather_world_time` (`world_time`),
    KEY `weather_last_updated` (`last_updated`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `workerstatus` (
    `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `worker_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
    `success` int(11) NOT NULL,
    `fail` int(11) NOT NULL,
    `no_items` int(11) NOT NULL,
    `skip` int(11) NOT NULL,
    `captcha` int(11) NOT NULL,
    `last_modified` datetime NOT NULL,
    `message` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_scan_date` datetime NOT NULL,
    `latitude` double DEFAULT NULL,
    `longitude` double DEFAULT NULL,
    PRIMARY KEY (`username`),
    KEY `workerstatus_worker_name` (`worker_name`),
    KEY `workerstatus_last_modified` (`last_modified`),
    KEY `workerstatus_last_scan_date` (`last_scan_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE VIEW `v_trs_status` AS
    SELECT trs.`device_id`, dev.`name`, trs.`routePos`, trs.`routeMax`, trs.`area_id`,
    IF(trs.`idle` = 1, 'Idle', IFNULL(sa.`name`, 'Idle')) AS 'rmname',
    IF(trs.`idle` = 1, 'Idle', IFNULL(sa.`mode`, 'Idle')) AS 'mode',
    trs.`rebootCounter`, trs.`init`, trs.`currentSleepTime`,
    trs.`rebootingOption`, trs.`restartCounter`, trs.`globalrebootcount`, trs.`globalrestartcount`,
    UNIX_TIMESTAMP(trs.`lastPogoRestart`) AS 'lastPogoRestart',
    UNIX_TIMESTAMP(trs.`lastProtoDateTime`) AS 'lastProtoDateTime',
    UNIX_TIMESTAMP(trs.`lastPogoReboot`) AS 'lastPogoReboot',
    CONCAT(ROUND(ST_X(trs.`currentPos`), 5), ', ', ROUND(ST_Y(trs.`currentPos`), 5)) AS 'currentPos',
    CONCAT(ROUND(ST_X(trs.`lastPos`), 5), ', ', ROUND(ST_Y(trs.`lastPos`), 5)) AS 'lastPos',
    `currentPos` AS 'currentPos_raw',
    `lastPos` AS 'lastPos_raw'
    FROM `trs_status` trs
    INNER JOIN `settings_device` dev ON dev.`device_id` = trs.`device_id`
    LEFT JOIN `settings_area` sa ON sa.`area_id` = trs.`area_id`;