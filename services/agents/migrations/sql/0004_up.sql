-- 0004: identity resolution and retraction state (M0.7).

ALTER TABLE papers ADD COLUMN alt_dois text[] NOT NULL DEFAULT '{}';
ALTER TABLE papers ADD COLUMN is_preprint boolean NOT NULL DEFAULT false;
ALTER TABLE papers ADD COLUMN is_open_access boolean;
ALTER TABLE papers ADD COLUMN publication_types text[] NOT NULL DEFAULT '{}';
ALTER TABLE papers ADD COLUMN retraction_notice_dois text[] NOT NULL DEFAULT '{}';
CREATE INDEX papers_alt_dois_idx ON papers USING gin (alt_dois);

-- Which paper each staged record resolved to, and why records merged (provenance of the merge).
ALTER TABLE source_records ADD COLUMN paper_id uuid REFERENCES papers (id);
ALTER TABLE source_records ADD COLUMN merge_reasons text[] NOT NULL DEFAULT '{}';
CREATE INDEX source_records_paper_idx ON source_records (paper_id);
GRANT UPDATE ON source_records TO a9_worker;
