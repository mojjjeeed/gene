-- 0010: dossiers, sign-offs and exports (M4.1, M4.2).
CREATE TABLE dossiers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  version         integer NOT NULL CHECK (version >= 1),
  content         jsonb NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  UNIQUE (conversation_id, version),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
);

-- A dossier version is a record of what was reviewed: it can never be edited, only superseded by a new version.
CREATE FUNCTION dossier_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.content IS DISTINCT FROM OLD.content OR NEW.version <> OLD.version OR NEW.conversation_id <> OLD.conversation_id THEN
    RAISE EXCEPTION 'a dossier version is immutable; create a new version' USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER dossiers_no_edit BEFORE UPDATE ON dossiers FOR EACH ROW EXECUTE FUNCTION dossier_immutable();

CREATE TABLE signoffs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dossier_id    uuid NOT NULL,
  user_id       uuid NOT NULL,
  reviewer_name text NOT NULL CHECK (btrim(reviewer_name) <> ''),  -- a named human
  decision      text NOT NULL CHECK (decision IN ('approved', 'rejected')),
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (dossier_id, user_id) REFERENCES dossiers (id, user_id) ON DELETE CASCADE
);

CREATE TABLE exports (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dossier_id uuid NOT NULL,
  user_id    uuid NOT NULL,
  format     text NOT NULL CHECK (format <> ''),
  signoff_id uuid NOT NULL REFERENCES signoffs (id),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (dossier_id, user_id) REFERENCES dossiers (id, user_id) ON DELETE CASCADE
);

-- No export without an approved sign-off against THAT dossier version, enforced for every writer.
CREATE FUNCTION export_requires_signoff() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM signoffs s WHERE s.id = NEW.signoff_id AND s.dossier_id = NEW.dossier_id AND s.decision = 'approved') THEN
    RAISE EXCEPTION 'export refused: no approved sign-off for dossier %', NEW.dossier_id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER exports_need_signoff BEFORE INSERT ON exports FOR EACH ROW EXECUTE FUNCTION export_requires_signoff();

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['dossiers', 'signoffs', 'exports'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY %I ON %I TO a9_app USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id())', t || '_owner', t);
    EXECUTE format('CREATE POLICY %I ON %I TO a9_worker USING (true) WITH CHECK (true)', t || '_worker', t);
    EXECUTE format('GRANT SELECT, INSERT ON %I TO a9_app, a9_worker', t);
  END LOOP;
END $$;
