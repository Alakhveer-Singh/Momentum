-- Run once on the server to create the database and app user:
--   mysql -u root -p < mysql_setup.sql
-- Change DB_PASSWORD_HERE to a real password before running, and use the
-- same value for DB_PASSWORD in your .env.

CREATE DATABASE IF NOT EXISTS quibus_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'quibus'@'localhost' IDENTIFIED BY 'DB_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON quibus_django.* TO 'quibus'@'localhost';
FLUSH PRIVILEGES;
