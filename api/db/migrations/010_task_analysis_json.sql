-- 010: Add analysis_json column to tasks table for storing post-run analysis results.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS analysis_json JSONB;
