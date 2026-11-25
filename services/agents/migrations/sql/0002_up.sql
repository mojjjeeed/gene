-- 0002: durable run events and job leases (M0.3).
--
-- Events are written in the same transaction as the state change they describe. seq comes from
-- runs.last_seq, bumped atomically, so it is monotonic per run by construction. Postgres is the
-- source of truth for replay; Redis only wakes live listeners.

ALTER TABLE runs ADD COLUMN last_seq integer NOT NULL DEFAULT 0 CHECK (last_seq >= 0);

CREATE TABLE run_events (
  run_id     uuid NOT NULL,
  seq        integer NOT NULL CHECK (seq >= 1),
  user_id    uuid NOT NULL,
  type       text NOT NULL CHECK (type IN (
               'stage_started', 'progress', 'partial_result', 'needs_input',
               'stage_finished', 'run_failed', 'run_finished')),
  data       jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, seq),
  FOREIGN KEY (run_id, user_id) REFERENCES runs (id, user_id) ON DELETE CASCADE
);

ALTER TABLE run_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_events FORCE ROW LEVEL SECURITY;
CREATE POLICY run_events_owner_read ON run_events FOR SELECT TO a9_app USING (user_id = app_user_id());
CREATE POLICY run_events_worker ON run_events TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT ON run_events TO a9_app;
GRANT SELECT, INSERT ON run_events TO a9_worker;

-- A worker holds a job by leasing it: heartbeat_at is refreshed while it works, and attempts is the
-- fencing token. A job whose heartbeat is stale can be taken over; the old holder's writes then
-- fail the fence. checkpoint is the job's own resume state.
ALTER TABLE jobs ADD COLUMN heartbeat_at timestamptz;
ALTER TABLE jobs ADD COLUMN checkpoint jsonb NOT NULL DEFAULT '{}';
CREATE INDEX jobs_status_heartbeat_idx ON jobs (status, heartbeat_at);
