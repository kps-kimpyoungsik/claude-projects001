-- PostgreSQL 스키마 (2026-07-24 신설) — 검증 미확정, README.md 참조.
-- 하이브리드 {id 컬럼 + data JSONB} 전략 — 근거는 README.md "설계 원칙" 참조.

CREATE TABLE IF NOT EXISTS requirements (
    req_id TEXT PRIMARY KEY,
    doc_type_code TEXT NOT NULL,
    area_code TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_requirements_lifecycle_status ON requirements (lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_requirements_doc_area ON requirements (doc_type_code, area_code);

CREATE TABLE IF NOT EXISTS rechunk_queue (
    id SERIAL PRIMARY KEY,
    entry JSONB NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);

-- task_lock_store.py의 "path -> task_id" 배타 점유와 동일 구조(§4.3 impact_scope 배타 점유).
CREATE TABLE IF NOT EXISTS task_locks (
    path TEXT PRIMARY KEY,
    task_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_locks_task_id ON task_locks (task_id);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data JSONB NOT NULL
);
