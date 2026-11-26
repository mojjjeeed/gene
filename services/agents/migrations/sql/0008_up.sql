-- 0008: extracted claims and the extraction cache (M1.3).
-- The cache is keyed by (chunk text hash, extractor version): chunks are global, so a re-run on the same
-- corpus, or the same literature in another conversation, costs nothing.
CREATE TABLE extractions (
  chunk_hash        text NOT NULL CHECK (chunk_hash <> ''),
  extractor_version text NOT NULL CHECK (extractor_version <> ''),
  claims            jsonb NOT NULL,  -- offsets RELATIVE to the chunk text, so identical text at another position reuses it
  created_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (chunk_hash, extractor_version)
);

CREATE TABLE claims (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id         uuid NOT NULL REFERENCES chunks (id) ON DELETE CASCADE,
  kind             text NOT NULL CHECK (kind IN ('measurement')),
  assay            text NOT NULL,
  qualifier        text,
  value            double precision NOT NULL,
  unit             text NOT NULL,
  value_nm         double precision NOT NULL,
  entity_raw       text,
  target_raw       text,
  sentence         text NOT NULL,
  -- Provenance envelope, no defaults: a claim without its full envelope must raise.
  paper_id         uuid NOT NULL REFERENCES papers (id) ON DELETE CASCADE,
  section_path     text[] NOT NULL CHECK (cardinality(section_path) >= 1),
  page             integer NOT NULL CHECK (page >= 1),
  char_start       integer NOT NULL CHECK (char_start >= 0),
  char_end         integer NOT NULL,
  parser_version   text NOT NULL CHECK (parser_version <> ''),
  extraction_model text NOT NULL CHECK (extraction_model <> ''),
  prompt_version   text NOT NULL CHECK (prompt_version <> ''),
  run_id           uuid NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT claim_span_ordered CHECK (char_end > char_start),
  UNIQUE (chunk_id, char_start, char_end, assay)
);
CREATE INDEX claims_paper_idx ON claims (paper_id);

ALTER TABLE extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE extractions FORCE ROW LEVEL SECURITY;
CREATE POLICY extractions_worker ON extractions TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON extractions TO a9_worker;

ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims FORCE ROW LEVEL SECURITY;
CREATE POLICY claims_via_membership ON claims FOR SELECT TO a9_app
  USING (EXISTS (SELECT 1 FROM chunk_memberships m WHERE m.chunk_id = claims.chunk_id));
CREATE POLICY claims_worker ON claims TO a9_worker USING (true) WITH CHECK (true);
GRANT SELECT ON claims TO a9_app;
GRANT SELECT, INSERT ON claims TO a9_worker;
