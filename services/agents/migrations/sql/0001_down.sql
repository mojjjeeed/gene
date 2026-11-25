-- Reverse of 0001. Roles are cluster-level and shared, so they are left in place.
DROP TABLE IF EXISTS
  audit_log,
  screening_verdicts,
  chunk_memberships,
  chunks,
  paper_assets,
  papers,
  search_plans,
  jobs,
  messages,
  runs,
  conversations,
  projects,
  users
CASCADE;

DROP FUNCTION IF EXISTS audit_log_append_only();
DROP FUNCTION IF EXISTS require_full_text_licence();
DROP FUNCTION IF EXISTS app_user_id();
