-- 0003: staging for records returned by literature sources, before identity resolution and dedup (M0.7).
-- One row per (run, source, source_id); a re-run of the same search is a no-op.

CREATE TABLE source_records (
  run_id     uuid NOT NULL,
  user_id    uuid NOT NULL,
  source     text NOT NULL CHECK (source <> ''),
  source_id  text NOT NULL CHECK (source_id <> ''),
  record     jsonb NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, source, source_id),
  FOREIGN KEY (run_id, user_id) REFERENCES runs (id, user_id) ON DELETE CASCADE
);

ALTER TABLE source_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_records FORCE ROW LEVEL SECURITY;
CREATE POLICY source_records_owner_read ON source_records FOR SELECT TO a9_app USING (user_id = app_user_id());
CREATE POLICY source_records_worker ON source_records TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT ON source_records TO a9_app;
GRANT SELECT, INSERT ON source_records TO a9_worker;
