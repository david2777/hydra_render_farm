-- MySQL dump 10.13  Distrib 8.0.22, for Win64 (x86_64)
--
-- Host: 192.168.1.200    Database: hydra
-- ------------------------------------------------------
-- Server version	8.0.23

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `capabilities`
--

DROP TABLE IF EXISTS `capabilities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `capabilities` (
  `name` varchar(45) NOT NULL,
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Table tos tore render node capabilities, eg Maya, VRay, Redshift, Windows, Linux, etc. ';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `jobs`
--

DROP TABLE IF EXISTS `jobs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `jobs` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'ID for the job, Primary Key, Auto Incremented',
  `name` varchar(256) NOT NULL DEFAULT 'HydraJob' COMMENT 'Nice name of the job for display in FarmView',
  `owner` varchar(128) NOT NULL DEFAULT 'HydraUser' COMMENT 'User name of job''s owner',
  `status` char(1) NOT NULL DEFAULT 'U' COMMENT 'Status of the job',
  `creation_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Time the job was created',
  `requirements` varchar(256) NOT NULL DEFAULT '' COMMENT 'Requirements for the job, eg. Redshift, Maya, Nuke, etc',
  `args` varchar(512) DEFAULT NULL COMMENT 'The base argments, eg. -x 1280 -y 720 -cam "TestCam" etc.',
  `task_file` varchar(512) DEFAULT NULL COMMENT 'The task file to be rendered, eg. the Maya file, Nuke script, etc',
  `priority` int NOT NULL DEFAULT '50' COMMENT 'Priority of the job, higher priority jobs will be executed first',
  `max_nodes` int NOT NULL DEFAULT '0' COMMENT 'Max nodes a job should run on',
  `timeout` int NOT NULL DEFAULT '0' COMMENT 'Timeout measured in seconds, 0 = None',
  `failed_nodes` varchar(512) NOT NULL DEFAULT '' COMMENT 'A list of nodes that the job has failed on, each node delimited by a single space. ',
  `attempts` int NOT NULL DEFAULT '0' COMMENT 'Number of times a job has been attempted and failed.',
  `max_attempts` int NOT NULL DEFAULT '10' COMMENT 'Maximum attempts before a job is stopped as Error.',
  `archived` tinyint(1) NOT NULL DEFAULT '0' COMMENT 'Mark a job as archived, 0 = False, 1 = True',
  `task_total` int NOT NULL DEFAULT '1' COMMENT 'Total number of tasks',
  `task_done` int NOT NULL DEFAULT '0' COMMENT 'Number of tasks complete',
  `start_frame` int DEFAULT NULL COMMENT 'The start frame of the job',
  `end_frame` int DEFAULT NULL COMMENT 'The end frame of the job',
  `by_frame` int DEFAULT NULL COMMENT 'Render each x frame',
  `render_layers` varchar(128) DEFAULT NULL COMMENT 'Render layers separated by commas',
  `mpf` time DEFAULT NULL COMMENT 'Minute per frame',
  `output_directory` varchar(512) DEFAULT NULL,
  `project` varchar(512) DEFAULT NULL,
  `script` varchar(2048) DEFAULT NULL,
  `mode` varchar(45) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8 COMMENT='Table for storing jobs';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `render_nodes`
--

DROP TABLE IF EXISTS `render_nodes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `render_nodes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `host` varchar(80) NOT NULL COMMENT 'Host name of the render node',
  `status` char(1) NOT NULL DEFAULT 'O' COMMENT 'The one character abbreviation for the node''s status (Idle, Started, etc)',
  `min_priority` int NOT NULL DEFAULT '0' COMMENT 'Lowest priority task that can be run by this node',
  `platform` varchar(15) NOT NULL COMMENT 'System platform (eg win32)',
  `ip_addr` varchar(39) DEFAULT NULL COMMENT 'IP Address for the node, required if the node is enabled for rendering. Should be a static IP. ',
  `task_id` int DEFAULT NULL COMMENT 'The ID of the task currently running (if any)',
  `capabilities` varchar(255) DEFAULT '' COMMENT 'The render nodes current capabilities in alphabetical order. (ie VRay, RenderMan, SOuP)',
  `pulse` datetime DEFAULT NULL COMMENT 'The last time render node was known to be running, if ever',
  `software_version` varchar(255) DEFAULT NULL COMMENT 'The version of the hydra software running on this node',
  `is_render_node` int DEFAULT '0' COMMENT 'Is this node used for rendering, 0 = False 1 = True',
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  UNIQUE KEY `host_UNIQUE` (`host`),
  KEY `rendertask_key_idx` (`task_id`),
  CONSTRAINT `rendertask_key` FOREIGN KEY (`task_id`) REFERENCES `tasks` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8 COMMENT='Table to store render node records ';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tasks`
--

DROP TABLE IF EXISTS `tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tasks` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'The task id for this task. Auto incremented.',
  `job_id` int NOT NULL COMMENT 'The job_id for this task. ',
  `status` char(1) NOT NULL DEFAULT 'R' COMMENT 'Current task status',
  `priority` int NOT NULL DEFAULT '50',
  `host` varchar(128) DEFAULT NULL COMMENT 'Host the task is running on',
  `start_frame` int DEFAULT NULL COMMENT 'The start frame for this task',
  `end_frame` int DEFAULT NULL,
  `exit_code` int DEFAULT NULL COMMENT 'Exit code from the subprocess',
  `start_time` datetime DEFAULT NULL COMMENT 'Time the task started',
  `end_time` datetime DEFAULT NULL COMMENT 'The the task ended',
  `mpf` time DEFAULT NULL COMMENT 'Minute per frame',
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`),
  KEY `id_idx` (`job_id`),
  KEY `node_key_idx` (`host`),
  CONSTRAINT `job_id_key` FOREIGN KEY (`job_id`) REFERENCES `jobs` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8 COMMENT='Table to store tasks';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2021-03-08 23:07:41
