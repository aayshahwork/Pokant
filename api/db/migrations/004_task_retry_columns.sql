-- 004_task_retry_columns.sql
-- Adds retry tracking and error classification columns to the tasks table.

ALTER TABLE tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN retry_of_task_id UUID REFERENCES tasks(id);
ALTER TABLE tasks ADD COLUMN error_category VARCHAR(50);

CREATE INDEX idx_tasks_retry_of ON tasks(retry_of_task_id) WHERE retry_of_task_id IS NOT NULL;
