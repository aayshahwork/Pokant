-- 008_analytics_indexes.sql
-- Covering index for time-range fleet health analytics queries.
-- Uses INCLUDE to keep aggregation columns in the index leaf pages
-- without affecting B-tree sort order.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_analytics
    ON tasks (account_id, created_at DESC)
    INCLUDE (status, cost_cents, duration_ms, total_tokens_in, total_tokens_out,
             error_category, executor_mode, url, retry_count, retry_of_task_id);
