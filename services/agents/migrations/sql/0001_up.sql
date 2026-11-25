-- 0001: core schema, row-level security and the invariants from docs/CLAUDE.md.
--
-- Roles (cluster-level, created idempotently, never dropped by downgrade):
--   a9_app    request path. Row-level security applies; every query is scoped by app.user_id.
--   a9_worker trusted backend (ingestion, jobs). Isolation there comes from the repository layer.
-- The connection owner sets the role and user per transaction:
--   SET LOCAL ROLE a9_app; SELECT set_config('app.user_id', '<uuid>', true);
-- With app.user_id unset, app_user_id() is NULL and a9_app sees nothing (fail closed).

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'a9_app') THEN
    CREATE ROLE a9_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'a9_worker') THEN
    CREATE ROLE a9_worker NOLOGIN;
  END IF;
END
$$;

CREATE FUNCTION app_user_id() RETURNS uuid
  LANGUAGE sql STABLE
  AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

-- ---------------------------------------------------------------------------------------------
-- User-owned tables. Child tables reference (id, user_id) pairs so a row can never point at
-- another user's parent: foreign-key checks bypass RLS, a composite key does not.
-- ---------------------------------------------------------------------------------------------

CREATE TABLE users (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email      text NOT NULL UNIQUE CHECK (email <> ''),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  name       text NOT NULL CHECK (name <> ''),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id)
);

CREATE TABLE conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL,
  project_id uuid NOT NULL,
  title      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  FOREIGN KEY (project_id, user_id) REFERENCES projects (id, user_id) ON DELETE CASCADE
);

CREATE TABLE runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('ingest', 'design', 'dossier')),
  status          text NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'running', 'needs_input', 'failed', 'finished')),
  -- Named reduced-coverage notes ([{source, reason}]). A source outage lands here, not in status.
  coverage_notes  jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(coverage_notes) = 'array'),
  thread_id       text,
  trace_id        text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
);

CREATE TABLE messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  role            text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content         text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
);

CREATE TABLE jobs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL,
  run_id     uuid NOT NULL,
  -- Deterministic from the job's inputs. A retry inserts the same key and is a no-op.
  job_key    text NOT NULL UNIQUE CHECK (job_key <> ''),
  kind       text NOT NULL CHECK (kind <> ''),
  status     text NOT NULL DEFAULT 'queued'
             CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  attempts   integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  payload    jsonb NOT NULL DEFAULT '{}',
  result     jsonb,
  error      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (run_id, user_id) REFERENCES runs (id, user_id) ON DELETE CASCADE
);

CREATE TABLE search_plans (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  version         integer NOT NULL CHECK (version >= 1),
  plan            jsonb NOT NULL,
  approved_by     uuid REFERENCES users (id),
  approved_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conversation_id, version),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE,
  CONSTRAINT plan_approval_complete CHECK ((approved_by IS NULL) = (approved_at IS NULL)),
  CONSTRAINT plan_approved_by_owner CHECK (approved_by IS NULL OR approved_by = user_id)
);

-- ---------------------------------------------------------------------------------------------
-- Global tables: papers and chunks are stored once and shared. Users reach chunks only through
-- their own conversation memberships.
-- ---------------------------------------------------------------------------------------------

CREATE TABLE papers (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doi                 text CHECK (doi = lower(doi)),
  pmid                text,
  pmcid               text,
  arxiv_id            text,
  title               text NOT NULL CHECK (title <> ''),
  abstract            text,
  journal             text,
  year                integer,
  source              text NOT NULL CHECK (source <> ''),
  -- Licence string as recorded from the source. NULL means unknown.
  licence             text,
  -- Set by the licence evaluator. Full text may be stored only when this is true.
  full_text_allowed   boolean NOT NULL DEFAULT false,
  abstract_only       boolean NOT NULL DEFAULT true,
  -- Retracted work is flagged and kept, never dropped.
  retraction_status   text NOT NULL DEFAULT 'none'
                      CHECK (retraction_status IN ('none', 'retracted', 'withdrawn', 'expression_of_concern')),
  retraction_checked_at timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT full_text_needs_licence CHECK (NOT full_text_allowed OR licence IS NOT NULL)
);
CREATE UNIQUE INDEX papers_doi_key ON papers (doi) WHERE doi IS NOT NULL;
CREATE UNIQUE INDEX papers_pmid_key ON papers (pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX papers_pmcid_key ON papers (pmcid) WHERE pmcid IS NOT NULL;
CREATE UNIQUE INDEX papers_arxiv_id_key ON papers (arxiv_id) WHERE arxiv_id IS NOT NULL;

CREATE TABLE paper_assets (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id   uuid NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
  kind       text NOT NULL CHECK (kind IN ('original_pdf', 'grobid_tei', 'figure', 'fulltext_html')),
  object_key text NOT NULL CHECK (object_key <> ''),
  sha256     text NOT NULL CHECK (sha256 <> ''),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (paper_id, kind, object_key)
);

CREATE TABLE chunks (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id       uuid NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
  kind           text NOT NULL
                 CHECK (kind IN ('abstract', 'body', 'table', 'table_linearised', 'figure_caption')),
  text           text NOT NULL CHECK (text <> ''),
  text_hash      text NOT NULL CHECK (text_hash <> ''),
  -- Provenance envelope. Deliberately no defaults: a chunk without a complete envelope must raise.
  section_path   text[] NOT NULL CHECK (cardinality(section_path) >= 1),
  page           integer NOT NULL CHECK (page >= 1),
  char_start     integer NOT NULL CHECK (char_start >= 0),
  char_end       integer NOT NULL,
  parser_version text NOT NULL CHECK (parser_version <> ''),
  extraction_model text NOT NULL CHECK (extraction_model <> ''),
  prompt_version text NOT NULL CHECK (prompt_version <> ''),
  -- Run that produced the chunk. Not a foreign key: user deletion must not be blocked by,
  -- or cascade into, shared chunks. The audit log keeps the run record.
  run_id         uuid NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chunk_span_ordered CHECK (char_end > char_start),
  UNIQUE (paper_id, kind, parser_version, char_start, char_end)
);
CREATE INDEX chunks_paper_id_idx ON chunks (paper_id);
CREATE INDEX chunks_text_hash_idx ON chunks (text_hash);

-- Licence check before any full-text write. Abstracts are allowed on any paper; everything
-- derived from full text requires a recorded licence that permits storing it.
CREATE FUNCTION require_full_text_licence() RETURNS trigger
  LANGUAGE plpgsql
  AS $$
BEGIN
  -- Row triggers run before NOT NULL checks; let those report a missing paper or kind.
  IF NEW.paper_id IS NULL OR NEW.kind IS NULL THEN
    RETURN NEW;
  END IF;
  IF TG_TABLE_NAME = 'chunks' AND NEW.kind = 'abstract' THEN
    RETURN NEW;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM papers p
    WHERE p.id = NEW.paper_id AND p.licence IS NOT NULL AND p.full_text_allowed
  ) THEN
    RAISE EXCEPTION 'licence missing or does not permit storing full text for paper %', NEW.paper_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER paper_assets_licence BEFORE INSERT OR UPDATE ON paper_assets
  FOR EACH ROW EXECUTE FUNCTION require_full_text_licence();
CREATE TRIGGER chunks_licence BEFORE INSERT OR UPDATE ON chunks
  FOR EACH ROW EXECUTE FUNCTION require_full_text_licence();

CREATE TABLE chunk_memberships (
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  chunk_id        uuid NOT NULL REFERENCES chunks (id) ON DELETE CASCADE,
  ingested_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (conversation_id, chunk_id),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE
);
CREATE INDEX chunk_memberships_chunk_idx ON chunk_memberships (chunk_id);

CREATE TABLE screening_verdicts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  conversation_id uuid NOT NULL,
  paper_id        uuid NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
  verdict         text NOT NULL CHECK (verdict IN ('include', 'exclude', 'unsure')),
  reason          text NOT NULL CHECK (reason <> ''),
  decided_by      text NOT NULL CHECK (decided_by IN ('model', 'user')),
  model           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- A user override is a second row (decided_by = 'user'), never an overwrite of the model verdict.
  UNIQUE (conversation_id, paper_id, decided_by),
  FOREIGN KEY (conversation_id, user_id) REFERENCES conversations (id, user_id) ON DELETE CASCADE,
  CONSTRAINT model_verdict_names_model CHECK (decided_by <> 'model' OR model IS NOT NULL)
);

-- Append-only: UPDATE, DELETE and TRUNCATE raise for every role, owner included.
CREATE TABLE audit_log (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts             timestamptz NOT NULL DEFAULT now(),
  -- No foreign key: the log must survive deletion of the user's data.
  user_id        uuid,
  actor          text NOT NULL CHECK (actor <> ''),
  action         text NOT NULL CHECK (action <> ''),
  entity_type    text NOT NULL CHECK (entity_type <> ''),
  entity_id      text,
  model_version  text,
  prompt_version text,
  detail         jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX audit_log_user_ts_idx ON audit_log (user_id, ts);

CREATE FUNCTION audit_log_append_only() RETURNS trigger
  LANGUAGE plpgsql
  AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only();

CREATE INDEX conversations_user_idx ON conversations (user_id);
CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
CREATE INDEX runs_conversation_idx ON runs (conversation_id);
CREATE INDEX jobs_run_idx ON jobs (run_id);
CREATE INDEX screening_verdicts_paper_idx ON screening_verdicts (paper_id);

-- ---------------------------------------------------------------------------------------------
-- Row-level security. FORCE so the table owner is subject to it too (superusers still bypass,
-- which is why tests and the app switch to a9_app with SET ROLE).
-- ---------------------------------------------------------------------------------------------

-- users: a request sees only its own row.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self ON users TO a9_app
  USING (id = app_user_id()) WITH CHECK (id = app_user_id());

-- user-owned tables: scoped on user_id, for reads and writes.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'projects', 'conversations', 'runs', 'messages', 'jobs', 'search_plans',
    'chunk_memberships', 'screening_verdicts'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I TO a9_app USING (user_id = app_user_id()) WITH CHECK (user_id = app_user_id())',
      t || '_owner', t);
    EXECUTE format('CREATE POLICY %I ON %I TO a9_worker USING (true) WITH CHECK (true)', t || '_worker', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO a9_app, a9_worker', t);
  END LOOP;
END
$$;

-- audit_log: users read and append their own entries; workers append for anyone.
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_log_read_own ON audit_log FOR SELECT TO a9_app USING (user_id = app_user_id());
CREATE POLICY audit_log_append_own ON audit_log FOR INSERT TO a9_app WITH CHECK (user_id = app_user_id());
CREATE POLICY audit_log_worker ON audit_log TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON audit_log TO a9_app, a9_worker;

-- chunks and paper assets: a request sees only what its own memberships reach. The subqueries
-- run under the caller's RLS, so memberships are already filtered to the caller.
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY chunks_via_membership ON chunks FOR SELECT TO a9_app
  USING (EXISTS (SELECT 1 FROM chunk_memberships m WHERE m.chunk_id = chunks.id));
CREATE POLICY chunks_worker ON chunks TO a9_worker USING (true) WITH CHECK (true);

ALTER TABLE paper_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_assets FORCE ROW LEVEL SECURITY;
CREATE POLICY paper_assets_via_membership ON paper_assets FOR SELECT TO a9_app
  USING (EXISTS (SELECT 1 FROM chunks c WHERE c.paper_id = paper_assets.paper_id));
CREATE POLICY paper_assets_worker ON paper_assets TO a9_worker USING (true) WITH CHECK (true);

GRANT SELECT ON chunks, paper_assets TO a9_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON chunks, paper_assets TO a9_worker;

-- papers: public bibliographic metadata, readable by every request; written by workers only.
GRANT SELECT ON papers TO a9_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON papers TO a9_worker;

GRANT SELECT, UPDATE ON users TO a9_app;
GRANT SELECT ON users TO a9_worker;
GRANT EXECUTE ON FUNCTION app_user_id() TO a9_app, a9_worker;
