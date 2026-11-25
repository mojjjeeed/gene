ALTER TABLE chunks DROP COLUMN IF EXISTS tokens;
ALTER TABLE papers DROP COLUMN IF EXISTS fulltext_note;
ALTER TABLE papers DROP COLUMN IF EXISTS fulltext_status;
DELETE FROM paper_assets WHERE kind IN ('jats_xml', 'document_json');
ALTER TABLE paper_assets DROP CONSTRAINT paper_assets_kind_check;
ALTER TABLE paper_assets ADD CONSTRAINT paper_assets_kind_check
  CHECK (kind IN ('original_pdf', 'grobid_tei', 'figure', 'fulltext_html'));
