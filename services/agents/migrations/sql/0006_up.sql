-- 0006: full-text ingest state (M1.1/M1.2).
ALTER TABLE paper_assets DROP CONSTRAINT paper_assets_kind_check;
ALTER TABLE paper_assets ADD CONSTRAINT paper_assets_kind_check
  CHECK (kind IN ('original_pdf', 'grobid_tei', 'figure', 'fulltext_html', 'jats_xml', 'document_json'));

ALTER TABLE papers ADD COLUMN fulltext_status text NOT NULL DEFAULT 'pending'
  CHECK (fulltext_status IN ('pending', 'parsed', 'abstract_only', 'not_permitted', 'failed'));
ALTER TABLE papers ADD COLUMN fulltext_note text;
ALTER TABLE chunks ADD COLUMN tokens integer NOT NULL DEFAULT 0 CHECK (tokens >= 0);
