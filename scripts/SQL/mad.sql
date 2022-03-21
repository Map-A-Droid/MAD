-- MySQL dump 10.16  Distrib 10.1.48-MariaDB, for debian-linux-gnu (x86_64)

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

SET FOREIGN_KEY_CHECKS=0;
SET NAMES utf8mb4;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('3d16f94ed34a');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `autoconfig_file`
--

DROP TABLE IF EXISTS `autoconfig_file`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `autoconfig_file` (
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data` longblob NOT NULL,
  PRIMARY KEY (`instance_id`,`name`),
  CONSTRAINT `fk_ac_f_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `autoconfig_logs`
--

DROP TABLE IF EXISTS `autoconfig_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `autoconfig_logs` (
  `log_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `instance_id` int(10) unsigned NOT NULL,
  `session_id` int(10) unsigned NOT NULL,
  `log_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `level` int(10) NOT NULL DEFAULT '2',
  `msg` varchar(1024) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`log_id`),
  KEY `k_acl` (`instance_id`,`session_id`),
  KEY `fk_ac_l_instance` (`session_id`),
  CONSTRAINT `fk_ac_l_instance` FOREIGN KEY (`session_id`) REFERENCES `autoconfig_registration` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `autoconfig_registration`
--

DROP TABLE IF EXISTS `autoconfig_registration`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `autoconfig_registration` (
  `instance_id` int(10) unsigned NOT NULL,
  `session_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `device_id` int(10) unsigned DEFAULT NULL,
  `ip` varchar(39) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` int(10) DEFAULT NULL,
  PRIMARY KEY (`session_id`),
  KEY `fk_ac_r_instance` (`instance_id`),
  KEY `fk_ac_r_device` (`device_id`),
  CONSTRAINT `fk_ac_r_device` FOREIGN KEY (`device_id`) REFERENCES `settings_device` (`device_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ac_r_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `filestore_chunks`
--

DROP TABLE IF EXISTS `filestore_chunks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `filestore_chunks` (
  `chunk_id` int(11) NOT NULL AUTO_INCREMENT,
  `filestore_id` int(11) NOT NULL,
  `size` int(11) NOT NULL,
  `data` longblob,
  PRIMARY KEY (`chunk_id`),
  UNIQUE KEY `chunk_id` (`chunk_id`,`filestore_id`),
  KEY `k_fs_chunks` (`filestore_id`),
  CONSTRAINT `fk_fs_chunks` FOREIGN KEY (`filestore_id`) REFERENCES `filestore_meta` (`filestore_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `filestore_meta`
--

DROP TABLE IF EXISTS `filestore_meta`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `filestore_meta` (
  `filestore_id` int(11) NOT NULL AUTO_INCREMENT,
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `size` int(11) NOT NULL,
  `mimetype` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`filestore_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gym`
--

DROP TABLE IF EXISTS `gym`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gym` (
  `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `team_id` smallint(6) NOT NULL,
  `guard_pokemon_id` smallint(6) NOT NULL,
  `slots_available` smallint(6) NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `total_cp` smallint(6) NOT NULL,
  `is_in_battle` tinyint(1) NOT NULL,
  `weather_boosted_condition` smallint(6) DEFAULT NULL,
  `last_modified` datetime NOT NULL,
  `last_scanned` datetime NOT NULL,
  `is_ex_raid_eligible` tinyint(1) DEFAULT NULL,
  `is_ar_scan_eligible` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`gym_id`),
  KEY `gym_last_modified` (`last_modified`),
  KEY `gym_last_scanned` (`last_scanned`),
  KEY `gym_latitude_longitude` (`latitude`,`longitude`),
  KEY `gym_team_id` (`team_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `gymdetails`
--

DROP TABLE IF EXISTS `gymdetails`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gymdetails` (
  `gym_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci,
  `url` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_scanned` datetime NOT NULL,
  PRIMARY KEY (`gym_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mad_apk_autosearch`
--

DROP TABLE IF EXISTS `mad_apk_autosearch`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `mad_apk_autosearch` (
  `usage` int(11) NOT NULL,
  `arch` int(11) NOT NULL,
  `version` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `url` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `download_status` tinyint(1) NOT NULL DEFAULT '0',
  `last_checked` datetime NOT NULL,
  PRIMARY KEY (`usage`,`arch`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `mad_apks`
--

DROP TABLE IF EXISTS `mad_apks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `mad_apks` (
  `filestore_id` int(11) NOT NULL AUTO_INCREMENT,
  `usage` int(11) NOT NULL,
  `arch` int(11) NOT NULL,
  `version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`filestore_id`),
  UNIQUE KEY `usage` (`usage`,`arch`),
  CONSTRAINT `fk_fs_apks` FOREIGN KEY (`filestore_id`) REFERENCES `filestore_meta` (`filestore_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `madmin_instance`
--

DROP TABLE IF EXISTS `madmin_instance`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `madmin_instance` (
  `instance_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`instance_id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;


--
-- Table structure for table `origin_hopper`
--

DROP TABLE IF EXISTS `origin_hopper`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `origin_hopper` (
  `origin` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_id` int(10) unsigned NOT NULL,
  PRIMARY KEY (`origin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pokemon`
--

DROP TABLE IF EXISTS `pokemon`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `fort_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cell_id` bigint(20) unsigned DEFAULT NULL,
  `seen_type` enum('wild','encounter','nearby_stop','nearby_cell','lure_wild','lure_encounter') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`encounter_id`),
  KEY `pokemon_spawnpoint_id` (`spawnpoint_id`),
  KEY `pokemon_pokemon_id` (`pokemon_id`),
  KEY `pokemon_last_modified` (`last_modified`),
  KEY `pokemon_latitude_longitude` (`latitude`,`longitude`),
  KEY `pokemon_disappear_time_pokemon_id` (`disappear_time`,`pokemon_id`),
  KEY `individual_attack` (`individual_attack`),
  KEY `pokemon_iv` (`individual_attack`,`individual_defense`,`individual_stamina`),
  KEY `pokemon_disappear_time` (`disappear_time`),
  KEY `pokemon_seen_type` (`seen_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pokemon_display`
--

DROP TABLE IF EXISTS `pokemon_display`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pokemon_display` (
  `encounter_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `pokemon` smallint(6) NOT NULL,
  `gender` smallint(6) DEFAULT NULL,
  `form` smallint(6) DEFAULT NULL,
  `costume` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`encounter_id`),
  KEY `ix_pokemon_display_pokemon` (`pokemon`),
  CONSTRAINT `pokemon_encounter_id_casc` FOREIGN KEY (`encounter_id`) REFERENCES `pokemon` (`encounter_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pokestop`
--

DROP TABLE IF EXISTS `pokestop`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pokestop` (
  `pokestop_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `last_modified` datetime NOT NULL,
  `lure_expiration` datetime DEFAULT NULL,
  `active_fort_modifier` smallint(6) DEFAULT NULL,
  `last_updated` datetime DEFAULT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `incident_start` datetime DEFAULT NULL,
  `incident_expiration` datetime DEFAULT NULL,
  `incident_grunt_type` smallint(1) DEFAULT NULL,
  `is_ar_scan_eligible` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`pokestop_id`),
  KEY `pokestop_last_modified` (`last_modified`),
  KEY `pokestop_lure_expiration` (`lure_expiration`),
  KEY `pokestop_active_fort_modifier` (`active_fort_modifier`),
  KEY `pokestop_last_updated` (`last_updated`),
  KEY `pokestop_latitude_longitude` (`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `raid`
--

DROP TABLE IF EXISTS `raid`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `evolution` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`gym_id`),
  KEY `raid_level` (`level`),
  KEY `raid_spawn` (`spawn`),
  KEY `raid_start` (`start`),
  KEY `raid_end` (`end`),
  KEY `raid_last_scanned` (`last_scanned`),
  KEY `raid_pokemon_id` (`pokemon_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `scannedlocation`
--

DROP TABLE IF EXISTS `scannedlocation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area`
--

DROP TABLE IF EXISTS `settings_area`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_area` (
  `area_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mode` enum('idle','iv_mitm','mon_mitm','pokestops','raids_mitm') COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`area_id`),
  KEY `fk_sa_instance` (`instance_id`),
  CONSTRAINT `fk_sa_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area_idle`
--

DROP TABLE IF EXISTS `settings_area_idle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_area_idle` (
  `area_id` int(10) unsigned NOT NULL,
  `geofence_included` int(10) unsigned NOT NULL,
  `routecalc` int(10) unsigned NOT NULL,
  PRIMARY KEY (`area_id`),
  KEY `fk_area_idle_geofence` (`geofence_included`),
  KEY `fk_area_idle_routecalc` (`routecalc`),
  CONSTRAINT `fk_area_idle` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_area_idle_geofence` FOREIGN KEY (`geofence_included`) REFERENCES `settings_geofence` (`geofence_id`),
  CONSTRAINT `fk_area_idle_routecalc` FOREIGN KEY (`routecalc`) REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area_iv_mitm`
--

DROP TABLE IF EXISTS `settings_area_iv_mitm`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `all_mons` tinyint(1) NOT NULL DEFAULT '0',
  `min_time_left_seconds` int(11) DEFAULT NULL,
  `encounter_all` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`area_id`),
  KEY `fk_ai_monid` (`monlist_id`),
  KEY `fk_area_iv_mitm_geofence` (`geofence_included`),
  KEY `fk_area_iv_mitm_routecalc` (`routecalc`),
  CONSTRAINT `fk_ai_monid` FOREIGN KEY (`monlist_id`) REFERENCES `settings_monivlist` (`monlist_id`),
  CONSTRAINT `fk_area_iv_mitm` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_area_iv_mitm_geofence` FOREIGN KEY (`geofence_included`) REFERENCES `settings_geofence` (`geofence_id`),
  CONSTRAINT `fk_area_iv_mitm_routecalc` FOREIGN KEY (`routecalc`) REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area_mon_mitm`
--

DROP TABLE IF EXISTS `settings_area_mon_mitm`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_area_mon_mitm` (
  `area_id` int(10) unsigned NOT NULL,
  `init` tinyint(1) NOT NULL,
  `geofence_included` int(10) unsigned NOT NULL,
  `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `routecalc` int(10) unsigned NOT NULL,
  `coords_spawns_known` tinyint(1) DEFAULT NULL,
  `speed` float DEFAULT NULL,
  `max_distance` float DEFAULT NULL,
  `delay_after_prio_event` int(11) DEFAULT NULL,
  `priority_queue_clustering_timedelta` float DEFAULT NULL,
  `remove_from_queue_backlog` float DEFAULT NULL,
  `starve_route` tinyint(1) DEFAULT NULL,
  `init_mode_rounds` int(11) DEFAULT NULL,
  `monlist_id` int(10) unsigned DEFAULT NULL,
  `all_mons` tinyint(1) NOT NULL DEFAULT '0',
  `min_time_left_seconds` int(11) DEFAULT NULL,
  `max_clustering` int(11) DEFAULT NULL,
  `include_event_id` int(11) DEFAULT NULL,
  `encounter_all` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`area_id`),
  KEY `fk_am_monid` (`monlist_id`),
  KEY `fk_area_mon_mitm_geofence` (`geofence_included`),
  KEY `fk_area_mon_mitm_routecalc` (`routecalc`),
  CONSTRAINT `fk_am_monid` FOREIGN KEY (`monlist_id`) REFERENCES `settings_monivlist` (`monlist_id`),
  CONSTRAINT `fk_area_mon_mitm` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_area_mon_mitm_geofence` FOREIGN KEY (`geofence_included`) REFERENCES `settings_geofence` (`geofence_id`),
  CONSTRAINT `fk_area_mon_mitm_routecalc` FOREIGN KEY (`routecalc`) REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area_pokestops`
--

DROP TABLE IF EXISTS `settings_area_pokestops`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_area_pokestops` (
  `area_id` int(10) unsigned NOT NULL,
  `geofence_included` int(10) unsigned NOT NULL,
  `geofence_excluded` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `routecalc` int(10) unsigned NOT NULL,
  `init` tinyint(1) NOT NULL,
  `level` tinyint(1) DEFAULT NULL,
  `route_calc_algorithm` enum('route','routefree') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `speed` float DEFAULT NULL,
  `max_distance` float DEFAULT NULL,
  `ignore_spinned_stops` tinyint(1) DEFAULT NULL,
  `cleanup_every_spin` tinyint(1) DEFAULT NULL,
  `layer` tinyint(3) NOT NULL DEFAULT '1',
  `enable_clustering` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`area_id`),
  KEY `fk_area_pokestops_geofence` (`geofence_included`),
  KEY `fk_area_pokestops_routecalc` (`routecalc`),
  CONSTRAINT `fk_area_pokestops` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_area_pokestops_geofence` FOREIGN KEY (`geofence_included`) REFERENCES `settings_geofence` (`geofence_id`),
  CONSTRAINT `fk_area_pokestops_routecalc` FOREIGN KEY (`routecalc`) REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_area_raids_mitm`
--

DROP TABLE IF EXISTS `settings_area_raids_mitm`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `all_mons` tinyint(1) NOT NULL DEFAULT '0',
  `encounter_all` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`area_id`),
  KEY `fk_ar_monid` (`monlist_id`),
  KEY `fk_area_raids_mitm_geofence` (`geofence_included`),
  KEY `fk_area_raids_mitm_routecalc` (`routecalc`),
  CONSTRAINT `fk_ar_monid` FOREIGN KEY (`monlist_id`) REFERENCES `settings_monivlist` (`monlist_id`),
  CONSTRAINT `fk_area_raids_mitm` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_area_raids_mitm_geofence` FOREIGN KEY (`geofence_included`) REFERENCES `settings_geofence` (`geofence_id`),
  CONSTRAINT `fk_area_raids_mitm_routecalc` FOREIGN KEY (`routecalc`) REFERENCES `settings_routecalc` (`routecalc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_auth`
--

DROP TABLE IF EXISTS `settings_auth`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_auth` (
  `auth_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `username` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`auth_id`),
  KEY `fk_sauth_instance` (`instance_id`),
  CONSTRAINT `fk_sauth_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_device`
--

DROP TABLE IF EXISTS `settings_device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `inventory_clear_rounds` int(11) DEFAULT NULL,
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
  `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `screendetection` tinyint(1) DEFAULT NULL,
  `logintype` enum('google','ptc') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ggl_login_mail` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `clear_game_data` tinyint(1) DEFAULT NULL,
  `account_rotation` tinyint(1) DEFAULT NULL,
  `rotation_waittime` float DEFAULT NULL,
  `rotate_on_lvl_30` tinyint(1) DEFAULT NULL,
  `injection_thresh_reboot` int(11) DEFAULT NULL,
  `enhanced_mode_quest` tinyint(1) DEFAULT '0',
  `enhanced_mode_quest_safe_items` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mac_address` varchar(17) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `interface_type` enum('lan','wlan') COLLATE utf8mb4_unicode_ci DEFAULT 'lan',
  `softbar_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `extended_permission_toggling` tinyint(1) NOT NULL,
  PRIMARY KEY (`device_id`),
  KEY `settings_device_ibfk_1` (`walker_id`),
  KEY `settings_device_ibfk_2` (`pool_id`),
  KEY `fk_sd_instance` (`instance_id`),
  CONSTRAINT `fk_sd_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE,
  CONSTRAINT `settings_device_ibfk_1` FOREIGN KEY (`walker_id`) REFERENCES `settings_walker` (`walker_id`),
  CONSTRAINT `settings_device_ibfk_2` FOREIGN KEY (`pool_id`) REFERENCES `settings_devicepool` (`pool_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_devicepool`
--

DROP TABLE IF EXISTS `settings_devicepool`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `inventory_clear_rounds` int(11) DEFAULT NULL,
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
  `startcoords_of_walker` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `injection_thresh_reboot` int(11) DEFAULT NULL,
  `screendetection` tinyint(1) DEFAULT NULL,
  `enhanced_mode_quest` tinyint(1) DEFAULT '0',
  `enhanced_mode_quest_safe_items` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`pool_id`),
  KEY `fk_sds_instance` (`instance_id`),
  CONSTRAINT `fk_sds_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_geofence`
--

DROP TABLE IF EXISTS `settings_geofence`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_geofence` (
  `geofence_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fence_type` enum('polygon','geojson') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'polygon',
  `fence_data` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`geofence_id`),
  UNIQUE KEY `name` (`name`,`instance_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_monivlist`
--

DROP TABLE IF EXISTS `settings_monivlist`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_monivlist` (
  `monlist_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`monlist_id`),
  KEY `fk_mil_instance` (`instance_id`),
  CONSTRAINT `fk_mil_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_monivlist_to_mon`
--

DROP TABLE IF EXISTS `settings_monivlist_to_mon`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_monivlist_to_mon` (
  `monlist_id` int(10) unsigned NOT NULL,
  `mon_id` int(11) NOT NULL,
  `mon_order` int(11) NOT NULL,
  PRIMARY KEY (`monlist_id`,`mon_id`),
  KEY `monlist_id` (`monlist_id`),
  KEY `mon_id` (`mon_id`),
  CONSTRAINT `settings_monivlist_to_mon_ibfk_1` FOREIGN KEY (`monlist_id`) REFERENCES `settings_monivlist` (`monlist_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_pogoauth`
--

DROP TABLE IF EXISTS `settings_pogoauth`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_pogoauth` (
  `instance_id` int(10) unsigned NOT NULL,
  `account_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `device_id` int(10) unsigned DEFAULT NULL,
  `login_type` enum('google','ptc') COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`account_id`),
  UNIQUE KEY `settings_pogoauth_u1` (`login_type`,`username`),
  KEY `fk_ac_g_instance` (`instance_id`),
  KEY `fk_spa_device_id` (`device_id`),
  KEY `settings_pogoauth_login_type` (`login_type`),
  CONSTRAINT `fk_ac_g_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_spa_device_id` FOREIGN KEY (`device_id`) REFERENCES `settings_device` (`device_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_routecalc`
--

DROP TABLE IF EXISTS `settings_routecalc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_routecalc` (
  `routecalc_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `recalc_status` tinyint(1) DEFAULT '0',
  `last_updated` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `routefile` longtext COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`routecalc_id`),
  KEY `settings_routecalc_instance_id` (`instance_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_walker`
--

DROP TABLE IF EXISTS `settings_walker`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_walker` (
  `walker_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`walker_id`),
  KEY `fk_w_instance` (`instance_id`),
  CONSTRAINT `fk_w_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_walker_to_walkerarea`
--

DROP TABLE IF EXISTS `settings_walker_to_walkerarea`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_walker_to_walkerarea` (
  `walker_id` int(10) unsigned NOT NULL,
  `walkerarea_id` int(10) unsigned NOT NULL,
  `area_order` int(11) NOT NULL,
  PRIMARY KEY (`walker_id`,`walkerarea_id`,`area_order`),
  KEY `walker_id` (`walker_id`),
  KEY `walkerarea_id` (`walkerarea_id`),
  CONSTRAINT `settings_walker_to_walkerarea_ibfk_1` FOREIGN KEY (`walker_id`) REFERENCES `settings_walker` (`walker_id`) ON DELETE CASCADE,
  CONSTRAINT `settings_walker_to_walkerarea_ibfk_2` FOREIGN KEY (`walkerarea_id`) REFERENCES `settings_walkerarea` (`walkerarea_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settings_walkerarea`
--

DROP TABLE IF EXISTS `settings_walkerarea`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `settings_walkerarea` (
  `walkerarea_id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `guid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `instance_id` int(10) unsigned NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `area_id` int(10) unsigned NOT NULL,
  `algo_type` enum('countdown','timer','round','period','coords','idle') COLLATE utf8mb4_unicode_ci NOT NULL,
  `algo_value` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `max_walkers` int(11) DEFAULT NULL,
  `eventid` int(11) DEFAULT NULL,
  PRIMARY KEY (`walkerarea_id`),
  KEY `fk_wa_instance` (`instance_id`),
  KEY `settings_walkerarea_ibfk_1` (`area_id`),
  CONSTRAINT `fk_wa_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE,
  CONSTRAINT `settings_walkerarea_ibfk_1` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `spawnpoint`
--

DROP TABLE IF EXISTS `spawnpoint`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_event`
--

DROP TABLE IF EXISTS `trs_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_event` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `event_name` varchar(100) DEFAULT NULL,
  `event_start` datetime DEFAULT NULL,
  `event_end` datetime DEFAULT NULL,
  `event_lure_duration` int(11) NOT NULL DEFAULT '30',
  PRIMARY KEY (`id`),
  KEY `trs_event_event_start_end` (`event_start`,`event_end`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_quest`
--

DROP TABLE IF EXISTS `trs_quest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `quest_reward` varchar(2560) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quest_template` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quest_task` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quest_pokemon_form_id` smallint(6) NOT NULL DEFAULT '0',
  `quest_pokemon_costume_id` smallint(6) NOT NULL DEFAULT '0',
  `quest_title` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `layer` tinyint(3) NOT NULL DEFAULT '1',
  PRIMARY KEY (`GUID`,`layer`),
  KEY `quest_type` (`quest_type`),
  KEY `trs_quest_quest_timestamp` (`quest_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_s2cells`
--

DROP TABLE IF EXISTS `trs_s2cells`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_s2cells` (
  `id` bigint(20) unsigned NOT NULL,
  `level` int(11) NOT NULL,
  `center_latitude` double NOT NULL,
  `center_longitude` double NOT NULL,
  `updated` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `trs_s2cells_center_lat_lng` (`center_latitude`,`center_longitude`),
  KEY `trs_s2cells_updated` (`updated`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_spawn`
--

DROP TABLE IF EXISTS `trs_spawn`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_spawn` (
  `spawnpoint` bigint(20) unsigned NOT NULL,
  `latitude` double NOT NULL,
  `longitude` double NOT NULL,
  `spawndef` int(11) NOT NULL DEFAULT '240',
  `earliest_unseen` int(6) NOT NULL,
  `last_scanned` datetime DEFAULT NULL,
  `first_detection` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_non_scanned` datetime DEFAULT NULL,
  `calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `eventid` int(11) NOT NULL DEFAULT '1',
  PRIMARY KEY (`spawnpoint`),
  KEY `event_lat_long` (`eventid`,`latitude`,`longitude`),
  KEY `trs_spawn_eventid` (`eventid`),
  KEY `trs_spawn_calc_endminsec` (`calc_endminsec`),
  KEY `trs_spawn_lat_lng` (`latitude`,`longitude`),
  KEY `trs_spawn_last_scanned` (`last_scanned`),
  KEY `trs_spawn_last_non_scanned` (`last_non_scanned`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_stats_detect`
--

DROP TABLE IF EXISTS `trs_stats_detect`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_stats_detect` (
  `id` int(100) NOT NULL AUTO_INCREMENT,
  `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `timestamp_scan` int(11) NOT NULL,
  `mon` int(255) DEFAULT NULL,
  `raid` int(255) DEFAULT NULL,
  `mon_iv` int(11) DEFAULT NULL,
  `quest` int(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `worker` (`worker`),
  KEY `trs_stats_detect_timestamp_scan` (`timestamp_scan`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_stats_detect_seen_type`
--

DROP TABLE IF EXISTS `trs_stats_detect_seen_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_stats_detect_seen_type` (
  `encounter_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `encounter` datetime DEFAULT NULL,
  `wild` datetime DEFAULT NULL,
  `nearby_stop` datetime DEFAULT NULL,
  `nearby_cell` datetime DEFAULT NULL,
  `lure_encounter` datetime DEFAULT NULL,
  `lure_wild` datetime DEFAULT NULL,
  PRIMARY KEY (`encounter_id`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_stats_detect_wild_mon_raw`
--

DROP TABLE IF EXISTS `trs_stats_detect_wild_mon_raw`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_stats_detect_wild_mon_raw` (
  `worker` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `encounter_id` bigint(20) unsigned NOT NULL,
  `count` int(11) NOT NULL,
  `is_shiny` tinyint(1) NOT NULL DEFAULT '0',
  `first_scanned` datetime NOT NULL,
  `last_scanned` datetime NOT NULL,
  PRIMARY KEY (`worker`,`encounter_id`),
  KEY `encounter_id` (`encounter_id`),
  KEY `ix_trs_stats_detect_wild_mon_raw_is_shiny` (`is_shiny`),
  KEY `trs_stats_detect_wild_mon_raw_is_shiny` (`is_shiny`),
  KEY `trs_stats_detect_wild_mon_raw_last_scanned` (`last_scanned`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_stats_location`
--

DROP TABLE IF EXISTS `trs_stats_location`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_stats_location` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `worker` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `timestamp_scan` int(11) NOT NULL,
  `location_ok` int(11) NOT NULL,
  `location_nok` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `worker` (`worker`),
  KEY `trs_stats_location_timestamp_scan` (`timestamp_scan`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_stats_location_raw`
--

DROP TABLE IF EXISTS `trs_stats_location_raw`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `transporttype` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `latlng` (`lat`,`lng`),
  KEY `trs_stats_location_raw_success` (`success`),
  KEY `trs_stats_location_raw_type` (`type`),
  KEY `trs_stats_location_raw_walker` (`walker`(191)),
  KEY `trs_stats_location_raw_worker` (`worker`),
  KEY `trs_stats_location_raw_period` (`period`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_status`
--

DROP TABLE IF EXISTS `trs_status`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  `lastProtoDateTime` datetime DEFAULT NULL,
  `lastPogoRestart` datetime DEFAULT NULL,
  `init` tinyint(1) DEFAULT NULL,
  `rebootingOption` tinyint(1) DEFAULT NULL,
  `restartCounter` int(11) DEFAULT NULL,
  `lastPogoReboot` datetime DEFAULT NULL,
  `globalrebootcount` int(11) DEFAULT '0',
  `globalrestartcount` int(11) DEFAULT '0',
  `currentSleepTime` int(11) NOT NULL DEFAULT '0',
  `last_softban_action` datetime DEFAULT NULL,
  `last_softban_action_location` geometry DEFAULT NULL,
  PRIMARY KEY (`device_id`),
  KEY `fk_ts_instance` (`instance_id`),
  KEY `fk_ts_areaid` (`area_id`),
  CONSTRAINT `fk_ts_areaid` FOREIGN KEY (`area_id`) REFERENCES `settings_area` (`area_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ts_dev_id` FOREIGN KEY (`device_id`) REFERENCES `settings_device` (`device_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ts_instance` FOREIGN KEY (`instance_id`) REFERENCES `madmin_instance` (`instance_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_usage`
--

DROP TABLE IF EXISTS `trs_usage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_usage` (
  `usage_id` int(10) NOT NULL AUTO_INCREMENT,
  `instance` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cpu` float DEFAULT NULL,
  `memory` float DEFAULT NULL,
  `garbage` int(5) DEFAULT NULL,
  `timestamp` int(11) DEFAULT NULL,
  PRIMARY KEY (`usage_id`),
  KEY `trs_usage_inst_ts` (`instance`,`timestamp`),
  KEY `trs_usage_instance` (`instance`),
  KEY `trs_usage_timestamp` (`timestamp`)
) ENGINE=InnoDB AUTO_INCREMENT=0 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `trs_visited`
--

DROP TABLE IF EXISTS `trs_visited`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `trs_visited` (
  `pokestop_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `origin` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`pokestop_id`,`origin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary table structure for view `v_trs_status`
--

DROP TABLE IF EXISTS `v_trs_status`;
/*!50001 DROP VIEW IF EXISTS `v_trs_status`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `v_trs_status` (
  `instance_id` tinyint NOT NULL,
  `device_id` tinyint NOT NULL,
  `name` tinyint NOT NULL,
  `routePos` tinyint NOT NULL,
  `routeMax` tinyint NOT NULL,
  `area_id` tinyint NOT NULL,
  `rmname` tinyint NOT NULL,
  `mode` tinyint NOT NULL,
  `rebootCounter` tinyint NOT NULL,
  `init` tinyint NOT NULL,
  `currentSleepTime` tinyint NOT NULL,
  `rebootingOption` tinyint NOT NULL,
  `restartCounter` tinyint NOT NULL,
  `globalrebootcount` tinyint NOT NULL,
  `globalrestartcount` tinyint NOT NULL,
  `lastPogoRestart` tinyint NOT NULL,
  `lastProtoDateTime` tinyint NOT NULL,
  `lastPogoReboot` tinyint NOT NULL,
  `currentPos` tinyint NOT NULL,
  `lastPos` tinyint NOT NULL,
  `currentPos_raw` tinyint NOT NULL,
  `lastPos_raw` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `versions`
--

DROP TABLE IF EXISTS `versions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `versions` (
  `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `val` smallint(6) NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `weather`
--

DROP TABLE IF EXISTS `weather`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
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
  KEY `weather_last_updated` (`last_updated`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Final view structure for view `v_trs_status`
--

/*!50001 DROP TABLE IF EXISTS `v_trs_status`*/;
/*!50001 DROP VIEW IF EXISTS `v_trs_status`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8 */;
/*!50001 SET character_set_results     = utf8 */;
/*!50001 SET collation_connection      = utf8_general_ci */;
/*!50001 VIEW `v_trs_status` AS select `trs`.`instance_id` AS `instance_id`,`trs`.`device_id` AS `device_id`,`dev`.`name` AS `name`,`trs`.`routePos` AS `routePos`,`trs`.`routeMax` AS `routeMax`,`trs`.`area_id` AS `area_id`,if((`trs`.`idle` = 1),'Idle',ifnull(`sa`.`name`,'Idle')) AS `rmname`,if((`trs`.`idle` = 1),'Idle',ifnull(`sa`.`mode`,'Idle')) AS `mode`,`trs`.`rebootCounter` AS `rebootCounter`,`trs`.`init` AS `init`,`trs`.`currentSleepTime` AS `currentSleepTime`,`trs`.`rebootingOption` AS `rebootingOption`,`trs`.`restartCounter` AS `restartCounter`,`trs`.`globalrebootcount` AS `globalrebootcount`,`trs`.`globalrestartcount` AS `globalrestartcount`,unix_timestamp(`trs`.`lastPogoRestart`) AS `lastPogoRestart`,unix_timestamp(`trs`.`lastProtoDateTime`) AS `lastProtoDateTime`,unix_timestamp(`trs`.`lastPogoReboot`) AS `lastPogoReboot`,concat(round(st_x(`trs`.`currentPos`),5),', ',round(st_y(`trs`.`currentPos`),5)) AS `currentPos`,concat(round(st_x(`trs`.`lastPos`),5),', ',round(st_y(`trs`.`lastPos`),5)) AS `lastPos`,`trs`.`currentPos` AS `currentPos_raw`,`trs`.`lastPos` AS `lastPos_raw` from ((`trs_status` `trs` join `settings_device` `dev` on((`dev`.`device_id` = `trs`.`device_id`))) left join `settings_area` `sa` on((`sa`.`area_id` = `trs`.`area_id`))) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
