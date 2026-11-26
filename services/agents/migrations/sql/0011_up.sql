-- 0011: screening gate: review items and pattern events (M3.6).
-- A blocked structure is never stored in `molecules` or shown; it lives only here, for a reviewer.
CREATE TABLE review_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('screening_hit')),
  rules           text[] NOT NULL CHECK (cardinality(rules) >= 1),
  smiles          text NOT NULL,
  inchikey        text NOT NULL,
  status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'cleared', 'upheld')),
  resolution      text,
  resolved_by     text,
  resolved_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE,
  CONSTRAINT resolved_means_named CHECK (status = 'open' OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);

CREATE TABLE screening_events (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    uuid NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('hit', 'near_miss')),
  rule       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX screening_events_user_idx ON screening_events (user_id, created_at);

ALTER TABLE review_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_items FORCE ROW LEVEL SECURITY;
-- The owner can SEE that a candidate is blocked and why; only the platform side can resolve it.
CREATE POLICY review_items_owner_read ON review_items FOR SELECT TO a9_app USING (user_id = app_user_id());
CREATE POLICY review_items_worker ON review_items TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT ON review_items TO a9_app;
GRANT SELECT, INSERT, UPDATE ON review_items TO a9_worker;

ALTER TABLE screening_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE screening_events FORCE ROW LEVEL SECURITY;
CREATE POLICY screening_events_worker ON screening_events TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON screening_events TO a9_worker;
