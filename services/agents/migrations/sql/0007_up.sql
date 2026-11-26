-- 0007: lexical arm of hybrid retrieval (Postgres full-text on chunks).
ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
