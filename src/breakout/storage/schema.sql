-- Schema do Breakout. Um arquivo, compatível com SQLite local E Turso/libSQL
-- (Turso é SQLite de verdade na nuvem, então o mesmo SQL roda nos dois).
--
-- A fronteira sagrada da arquitetura está codificada aqui:
--   VERDADE (append-only, insubstituível): videos, snapshots
--   DERIVADO (recomputável a partir da verdade): detections, labels, features
-- Você pode dropar a camada derivada inteira e reconstruí-la dos snapshots.

-- ─────────────────────────── VERDADE ───────────────────────────

-- Carteira de vídeos rastreados + metadados (insumo do Motor B).
CREATE TABLE IF NOT EXISTS videos (
    video_id            TEXT PRIMARY KEY,
    channel_id          TEXT,
    title               TEXT,
    duration_s          INTEGER,
    published_at        TEXT,               -- ISO8601 UTC
    channel_subscribers INTEGER DEFAULT 0,
    tags                TEXT    DEFAULT '',  -- vírgula-separado
    category            TEXT    DEFAULT 'unknown',
    thumbnail_url       TEXT,               -- Motor B multimodal (Fase 5): CV
    transcript          TEXT,               -- Motor B multimodal (Fase 5): legendas
    transcript_source   TEXT,               -- Fase 7: 'caption' | 'whisper' | NULL
    first_seen_at       TEXT,               -- quando entrou na carteira
    last_sampled_at     TEXT,               -- p/ a política de cadência
    active              INTEGER DEFAULT 1   -- 1 = ainda rastreando
);

-- Snapshots: a série temporal crua. APPEND-ONLY. É a fonte da verdade.
-- PK (video_id, at) => recoletar o mesmo instante sobrescreve, nunca duplica.
CREATE TABLE IF NOT EXISTS snapshots (
    video_id TEXT    NOT NULL,
    at       TEXT    NOT NULL,              -- ISO8601 UTC
    views    INTEGER NOT NULL,
    likes    INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    PRIMARY KEY (video_id, at)
);
CREATE INDEX IF NOT EXISTS idx_snap_video_time ON snapshots (video_id, at);

-- Diário de coleta: conta a história de confiabilidade e habilita catch-up.
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    kind              TEXT,                 -- 'discover' | 'sample'
    videos_touched    INTEGER DEFAULT 0,
    snapshots_written INTEGER DEFAULT 0,
    quota_units       INTEGER DEFAULT 0,    -- orçamento gasto na rodada
    ok                INTEGER DEFAULT 1,
    note              TEXT
);

-- ─────────────────────── CONFIGURAÇÃO ───────────────────────────
-- Nem verdade coletada, nem derivado de snapshot: preferência operacional
-- de produto. Única tabela que o dashboard tem permissão de ESCREVER (Fase
-- 7) — exceção documentada ao "dashboard read-only" da Seção 5 do CLAUDE.md,
-- justamente porque não é dado colhido, é config (trocar nicho não arrisca
-- corromper o núcleo append-only sagrado).
CREATE TABLE IF NOT EXISTS discover_topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT    NOT NULL,
    language   TEXT,                          -- ISO 639-1 (ex: 'pt'), opcional
    active     INTEGER DEFAULT 1,              -- 0 = pausado sem apagar histórico
    created_at TEXT
);

-- ────────────────────────── DERIVADO ───────────────────────────
-- Preenchido pelos jobs offline. Sempre reconstruível dos snapshots.

CREATE TABLE IF NOT EXISTS detections (
    video_id    TEXT NOT NULL,
    detector    TEXT NOT NULL,             -- 'baseline_accel', 'cusum', ...
    at_hours    REAL NOT NULL,             -- quando o detector disparou
    score       REAL,
    computed_at TEXT,
    PRIMARY KEY (video_id, detector)
);

CREATE TABLE IF NOT EXISTS labels (
    video_id    TEXT PRIMARY KEY,
    is_viral    INTEGER,
    definition  TEXT,                       -- qual regra de rótulo gerou isto
    computed_at TEXT
);
