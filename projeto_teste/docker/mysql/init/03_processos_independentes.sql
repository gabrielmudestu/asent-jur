SET @fk_exists := (
    SELECT COUNT(*)
    FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND CONSTRAINT_NAME = 'fk_empresa_processo'
);

SET @drop_fk_sql := IF(
    @fk_exists > 0,
    'ALTER TABLE processos DROP FOREIGN KEY fk_empresa_processo',
    'SELECT 1'
);

PREPARE drop_fk_stmt FROM @drop_fk_sql;
EXECUTE drop_fk_stmt;
DEALLOCATE PREPARE drop_fk_stmt;

ALTER TABLE processos
    MODIFY COLUMN empresa_id INT NULL;

UPDATE processos
SET empresa_id = NULL;
