-- 请由 MySQL 管理员执行，并替换强密码。
CREATE DATABASE IF NOT EXISTS ai_education
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'ai_education_app'@'localhost' IDENTIFIED BY 'change_me';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON ai_education.* TO 'ai_education_app'@'localhost';
FLUSH PRIVILEGES;

