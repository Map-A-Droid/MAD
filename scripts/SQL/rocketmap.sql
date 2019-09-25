SET FOREIGN_KEY_CHECKS=0;
SET NAMES utf8mb4;

CREATE TABLE `gomap` (
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `gym` (
  `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `team_id` smallint(6) NOT NULL DEFAULT 0,
  `guard_pokemon_id` smallint(6) NOT NULL DEFAULT 0,
  `slots_available` smallint(6) NOT NULL DEFAULT 6,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `total_cp` smallint(6) NOT NULL DEFAULT 0,
  `is_in_battle` tinyint(1) NOT NULL DEFAULT 0,
  `gender` smallint(6) DEFAULT NULL,
  `form` smallint(6) DEFAULT NULL,
  `costume` smallint(6) DEFAULT NULL,
  `weather_boosted_condition` smallint(6) DEFAULT NULL,
  `shiny` tinyint(1) DEFAULT NULL,
  `last_modified` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_scanned` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`gym_id`),
  KEY `gym_last_modified` (`last_modified`),
  KEY `gym_last_scanned` (`last_scanned`),
  KEY `gym_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `gymdetails` (
  `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `url` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_scanned` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`gym_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `gymmember` (
  `gym_id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pokemon_uid` bigint(20) unsigned NOT NULL,
  `last_scanned` datetime NOT NULL,
  `deployment_time` datetime NOT NULL,
  `cp_decayed` smallint(6) NOT NULL,
  KEY `gymmember_gym_id` (`gym_id`),
  KEY `gymmember_pokemon_uid` (`pokemon_uid`),
  KEY `gymmember_last_scanned` (`last_scanned`)
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


CREATE TABLE `mainworker` (
  `worker_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message` longtext COLLATE utf8mb4_unicode_ci DEFAULT NULL,
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
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `last_modified` datetime DEFAULT CURRENT_TIMESTAMP,
  `lure_expiration` datetime DEFAULT NULL,
  `active_fort_modifier` smallint(6) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `name` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
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
  CONSTRAINT `scanspawnpoint_ibfk_1` FOREIGN KEY (`scannedlocation_id`) REFERENCES `scannedlocation` (`cellid`),
  CONSTRAINT `scanspawnpoint_ibfk_2` FOREIGN KEY (`spawnpoint_id`) REFERENCES `spawnpoint` (`id`)
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
  PRIMARY KEY (`GUID`),
  KEY `quest_type` (`quest_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `trs_spawn` (
  `spawnpoint` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `spawndef` int(11) NOT NULL DEFAULT 240,
  `earliest_unseen` int(6) NOT NULL,
  `last_scanned` datetime DEFAULT NULL,
  `first_detection` datetime NOT NULL DEFAULT current_timestamp(),
  `last_non_scanned` datetime DEFAULT NULL,
  `calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  UNIQUE KEY `spawnpoint_2` (`spawnpoint`),
  KEY `spawnpoint` (`spawnpoint`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `trs_spawnsightings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `encounter_id` bigint(20) unsigned NOT NULL,
  `spawnpoint_id` bigint(20) unsigned NOT NULL,
  `scan_time` datetime NOT NULL DEFAULT current_timestamp(),
  `tth_secs` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `trs_spawnpointdd_spawnpoint_id` (`spawnpoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `trs_status` (
  `origin` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `currentPos` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `lastPos` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `routePos` int(11) DEFAULT 1,
  `routeMax` int(11) DEFAULT 1,
  `routemanager` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rebootCounter` int(11) DEFAULT NULL,
  `lastProtoDateTime` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `lastPogoRestart` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `init` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rebootingOption` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `restartCounter` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `lastPogoReboot` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `globalrebootcount` int(11) DEFAULT 0,
  `globalrestartcount` int(11) DEFAULT 0,
  PRIMARY KEY (`origin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE `versions` (
  `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `val` smallint(6) NOT NULL
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
