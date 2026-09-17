"""PostgreSQL persistence for owner-requested Nami improvements."""
import json


DDL = """
CREATE TABLE IF NOT EXISTS nami_improvements(
  id BIGSERIAL PRIMARY KEY,
  requested_by TEXT NOT NULL,
  instruction TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'requested',
  branch TEXT,
  pr_number INTEGER,
  test_summary TEXT,
  deploy_sha TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


class ImprovementStore:
    def __init__(self, connect):
        self.connect=connect

    def init(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(DDL); conn.commit()

    def create(self, requested_by, instruction):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO nami_improvements(requested_by,instruction) VALUES(%s,%s) RETURNING id",(requested_by,instruction))
            row=cur.fetchone(); conn.commit(); return row[0]

    def update(self, improvement_id, *, state, branch=None, pr_number=None, test_summary=None, deploy_sha=None, metadata=None):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("""UPDATE nami_improvements SET state=%s, branch=COALESCE(%s,branch), pr_number=COALESCE(%s,pr_number), test_summary=COALESCE(%s,test_summary), deploy_sha=COALESCE(%s,deploy_sha), metadata=COALESCE(%s::jsonb,metadata), updated_at=NOW() WHERE id=%s""",(state,branch,pr_number,test_summary,deploy_sha,json.dumps(metadata) if metadata is not None else None,improvement_id))
            conn.commit()

    def latest_pending(self, requested_by):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("""SELECT id,instruction,state,branch,pr_number,test_summary,deploy_sha FROM nami_improvements WHERE requested_by=%s AND state NOT IN ('deployed','failed') ORDER BY id DESC LIMIT 1""",(requested_by,))
            return cur.fetchone()
