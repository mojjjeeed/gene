DROP INDEX IF EXISTS source_records_paper_idx;
ALTER TABLE source_records DROP COLUMN IF EXISTS merge_reasons;
ALTER TABLE source_records DROP COLUMN IF EXISTS paper_id;
DROP INDEX IF EXISTS papers_alt_dois_idx;
ALTER TABLE papers DROP COLUMN IF EXISTS retraction_notice_dois;
ALTER TABLE papers DROP COLUMN IF EXISTS publication_types;
ALTER TABLE papers DROP COLUMN IF EXISTS is_open_access;
ALTER TABLE papers DROP COLUMN IF EXISTS is_preprint;
ALTER TABLE papers DROP COLUMN IF EXISTS alt_dois;
