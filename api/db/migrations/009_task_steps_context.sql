-- Add JSONB context column to task_steps for storing structured step metadata
-- (desktop window info, LLM traces, API call details, etc.)

ALTER TABLE task_steps
    ADD COLUMN IF NOT EXISTS context jsonb;

COMMENT ON COLUMN task_steps.context IS 'Structured step context: desktop_action, llm_call, api_call, state_snapshot, etc.';
