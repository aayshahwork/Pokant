-- 007_alerts_table.sql
-- Server-side alert storage for aggregate anomaly detection.

CREATE TABLE IF NOT EXISTS alerts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    alert_type  VARCHAR(50) NOT NULL,
    message     TEXT NOT NULL,
    task_id     UUID REFERENCES tasks(id) ON DELETE SET NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for listing unacknowledged alerts per account (the primary query pattern)
CREATE INDEX IF NOT EXISTS idx_alerts_account_unacked
    ON alerts (account_id, acknowledged, created_at DESC)
    WHERE acknowledged = FALSE;

-- Index for evaluator dedup lookups (recent alerts by type per account)
CREATE INDEX IF NOT EXISTS idx_alerts_account_type_recent
    ON alerts (account_id, alert_type, created_at DESC);

-- RLS: accounts can only see their own alerts
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY alerts_account_isolation ON alerts
    USING (account_id = current_setting('app.account_id', TRUE)::UUID);

CREATE POLICY alerts_insert_policy ON alerts
    FOR INSERT
    WITH CHECK (account_id = current_setting('app.account_id', TRUE)::UUID);
