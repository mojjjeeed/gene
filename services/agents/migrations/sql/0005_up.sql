-- 0005: authors on papers, so the paper list does not have to dig through staged source records.
ALTER TABLE papers ADD COLUMN authors text[] NOT NULL DEFAULT '{}';
