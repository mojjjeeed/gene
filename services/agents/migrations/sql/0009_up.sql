-- 0009: model registry, candidate molecules, gate results and scores (M2.4, M3).
CREATE TABLE models (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL CHECK (name <> ''),
  version       text NOT NULL CHECK (version <> ''),
  endpoint      text NOT NULL CHECK (endpoint <> ''),
  -- What it was trained on and how far it can be trusted: required, so no model is anonymous.
  training_data text NOT NULL CHECK (training_data <> ''),
  calibrated_at timestamptz NOT NULL,
  domain_notes  text NOT NULL CHECK (domain_notes <> ''),
  card          jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (name, version)
);
GRANT SELECT ON models TO a9_app, a9_worker;
GRANT INSERT ON models TO a9_worker;

CREATE TABLE molecules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  smiles          text NOT NULL CHECK (smiles <> ''),
  inchikey        text NOT NULL CHECK (inchikey <> ''),
  run_id          uuid,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  UNIQUE (conversation_id, inchikey),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
);

CREATE TABLE molecule_gates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  molecule_id uuid NOT NULL,
  user_id     uuid NOT NULL,
  gate        text NOT NULL CHECK (gate <> ''),
  hard        boolean NOT NULL,
  passed      boolean NOT NULL,
  detail      jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (molecule_id, gate),
  FOREIGN KEY (molecule_id, user_id) REFERENCES molecules (id, user_id) ON DELETE CASCADE
);

-- A score cannot exist without the model that produced it, and in_domain is never null. Outside the
-- applicability domain there is NO number: a value with no support is worse than a blank.
CREATE TABLE molecule_scores (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  molecule_id   uuid NOT NULL,
  user_id       uuid NOT NULL,
  model_id      uuid NOT NULL REFERENCES models (id),
  endpoint      text NOT NULL CHECK (endpoint <> ''),
  value         double precision,
  lower         double precision,
  upper         double precision,
  coverage      double precision CHECK (coverage > 0 AND coverage < 1),
  in_domain     boolean NOT NULL,
  nn_similarity double precision NOT NULL CHECK (nn_similarity BETWEEN 0 AND 1),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (molecule_id, model_id, endpoint),
  FOREIGN KEY (molecule_id, user_id) REFERENCES molecules (id, user_id) ON DELETE CASCADE,
  CONSTRAINT no_number_outside_domain CHECK (in_domain OR (value IS NULL AND lower IS NULL AND upper IS NULL)),
  CONSTRAINT number_inside_domain CHECK (NOT in_domain OR (value IS NOT NULL AND lower IS NOT NULL AND upper IS NOT NULL AND lower <= value AND value <= upper))
);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['molecules', 'molecule_gates', 'molecule_scores'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY %I ON %I TO a9_app USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id())', t || '_owner', t);
    EXECUTE format('CREATE POLICY %I ON %I TO a9_worker USING (true) WITH CHECK (true)', t || '_worker', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO a9_app, a9_worker', t);
  END LOOP;
END
$$;
