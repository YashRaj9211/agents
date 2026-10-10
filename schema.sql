-- ============================================================================
-- Multi-Agent Orchestrator Platform - PostgreSQL Schema
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS citext;
-- CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector: enable when memory system is added

-- ───────── Identity ─────────
CREATE TABLE IF NOT EXISTS users (
  id             uuid PRIMARY KEY,                -- UUIDv7 generated app-side
  auth_provider  text NOT NULL,                   -- 'google', 'github', etc.
  auth_subject   text NOT NULL,                   -- provider's unique user ID
  handle         citext NOT NULL UNIQUE,
  full_name      text NOT NULL,
  avatar_url     text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz,
  UNIQUE (auth_provider, auth_subject)
);

CREATE TABLE IF NOT EXISTS workspaces (           -- future-proofs teams/multi-tenancy
  id          uuid PRIMARY KEY,
  name        text NOT NULL,
  owner_id    uuid NOT NULL REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id      uuid REFERENCES users(id) ON DELETE CASCADE,
  role         text NOT NULL DEFAULT 'member' CHECK (role IN ('owner','admin','member','viewer')),
  PRIMARY KEY (workspace_id, user_id)
);

-- ───────── Secrets (used by MCPs, browser profiles, tools) ─────────
CREATE TABLE IF NOT EXISTS credentials (
  id            uuid PRIMARY KEY,
  workspace_id  uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name          text NOT NULL,
  kind          text NOT NULL,                    -- 'api_key','oauth_token','basic'
  ciphertext    bytea NOT NULL,                   -- encrypted app-side (KMS/Fernet)
  key_id        text NOT NULL,                    -- which key encrypted it (rotation)
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, name)
);

-- ───────── Tools & MCPs ─────────
CREATE TABLE IF NOT EXISTS mcp_servers (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name           text NOT NULL,
  transport      text NOT NULL CHECK (transport IN ('stdio','sse','http')),
  url            text,
  command        text,
  args           jsonb NOT NULL DEFAULT '[]',
  env            jsonb NOT NULL DEFAULT '{}',
  credential_id  uuid REFERENCES credentials(id),
  status         text NOT NULL DEFAULT 'unknown' CHECK (status IN ('unknown','healthy','unhealthy','disabled')),
  last_health_at timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, name)
);

CREATE TABLE IF NOT EXISTS tools (
  id            uuid PRIMARY KEY,
  name          text NOT NULL,
  description   text,
  source        text NOT NULL CHECK (source IN ('builtin','mcp','custom')),
  mcp_server_id uuid REFERENCES mcp_servers(id) ON DELETE CASCADE,  -- NULL for builtin
  input_schema  jsonb NOT NULL DEFAULT '{}',
  is_active     boolean NOT NULL DEFAULT true,
  UNIQUE NULLS NOT DISTINCT (mcp_server_id, name)                   -- PG15+
);

-- ───────── Agent catalog + fleet ─────────
CREATE TABLE IF NOT EXISTS agent_definitions (
  id           text PRIMARY KEY,                  -- 'root_agent','browser_agent'
  name         text NOT NULL,
  description  text,
  kind         text NOT NULL DEFAULT 'worker' CHECK (kind IN ('root','worker','scheduler')),
  config       jsonb NOT NULL DEFAULT '{}',       -- model, system prompt ref, limits
  version      int  NOT NULL DEFAULT 1,
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_tools (          -- which agent may use which tool
  agent_id  text REFERENCES agent_definitions(id) ON DELETE CASCADE,
  tool_id   uuid REFERENCES tools(id) ON DELETE CASCADE,
  config    jsonb NOT NULL DEFAULT '{}',          -- per-agent overrides, approval rules
  PRIMARY KEY (agent_id, tool_id)
);

CREATE TABLE IF NOT EXISTS agent_instances (      -- the fleet: running workers
  id                uuid PRIMARY KEY,
  agent_id          text NOT NULL REFERENCES agent_definitions(id),
  workspace_id      uuid REFERENCES workspaces(id),
  status            text NOT NULL DEFAULT 'idle'
                    CHECK (status IN ('starting','idle','busy','draining','offline','error')),
  host              text,                          -- node/container id
  config_override   jsonb NOT NULL DEFAULT '{}',
  last_heartbeat_at timestamptz,
  started_at        timestamptz NOT NULL DEFAULT now(),
  stopped_at        timestamptz
);
CREATE INDEX IF NOT EXISTS idx_agent_instances_agent_status ON agent_instances (agent_id, status);

-- ───────── Conversations ─────────
CREATE TABLE IF NOT EXISTS sessions (
  id               uuid PRIMARY KEY,
  workspace_id     uuid NOT NULL REFERENCES workspaces(id),
  user_id          uuid NOT NULL REFERENCES users(id),
  primary_agent_id text REFERENCES agent_definitions(id),
  title            text,
  preview_text     text,                           -- denormalized for sidebar
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  last_message_at  timestamptz NOT NULL DEFAULT now(),
  created_at       timestamptz NOT NULL DEFAULT now(),
  deleted_at       timestamptz
);
CREATE INDEX IF NOT EXISTS sessions_sidebar ON sessions (user_id, last_message_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS messages (
  id              uuid PRIMARY KEY,
  session_id      uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  seq             bigint NOT NULL,                 -- strict ordering within session
  role            text NOT NULL CHECK (role IN ('user','assistant','system')),
  sender_user_id  uuid REFERENCES users(id),
  sender_agent_id text REFERENCES agent_definitions(id),
  run_id          uuid,                            -- FK added after agent_runs
  content         text NOT NULL DEFAULT '',
  metadata        jsonb NOT NULL DEFAULT '{}',     -- thought_process, UI hints
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, seq),
  CHECK (num_nonnulls(sender_user_id, sender_agent_id) <= 1)
);

-- ───────── Execution trace ─────────
CREATE TABLE IF NOT EXISTS agent_runs (
  id                 uuid PRIMARY KEY,
  session_id         uuid REFERENCES sessions(id) ON DELETE CASCADE,  -- NULL for scheduled/background runs
  trigger_message_id uuid REFERENCES messages(id),
  parent_run_id      uuid REFERENCES agent_runs(id),                  -- handoff tree
  agent_id           text NOT NULL REFERENCES agent_definitions(id),
  instance_id        uuid REFERENCES agent_instances(id),
  status             text NOT NULL DEFAULT 'running'
                     CHECK (status IN ('queued','running','completed','failed','cancelled')),
  error              jsonb,
  usage              jsonb NOT NULL DEFAULT '{}',   -- tokens, cost, latency
  started_at         timestamptz NOT NULL DEFAULT now(),
  finished_at        timestamptz
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_session_started ON agent_runs (session_id, started_at);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent ON agent_runs (parent_run_id);

-- Add delayed FK constraints
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_messages_run'
  ) THEN
    ALTER TABLE messages ADD CONSTRAINT fk_messages_run FOREIGN KEY (run_id) REFERENCES agent_runs(id);
  END IF;
END $$;

-- ───────── Browser profiles ─────────
CREATE TABLE IF NOT EXISTS browser_profiles (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  owner_id       uuid NOT NULL REFERENCES users(id),
  name           text NOT NULL,
  engine         text NOT NULL DEFAULT 'chromium' CHECK (engine IN ('chromium','firefox','webkit')),
  storage_uri    text,                             -- encrypted storageState / user-data-dir snapshot
  launch_options jsonb NOT NULL DEFAULT '{}',      -- viewport, proxy, UA, headless
  locked_by_run  uuid REFERENCES agent_runs(id) ON DELETE SET NULL, -- prevents two runs sharing one profile
  last_used_at   timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, name)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id           uuid PRIMARY KEY,
  run_id       uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  message_id   uuid REFERENCES messages(id),
  tool_id      uuid REFERENCES tools(id),
  tool_name    text NOT NULL,                      -- snapshot; survives tool deletion
  status       text NOT NULL DEFAULT 'running'
               CHECK (status IN ('pending_approval','running','completed','failed','cancelled')),
  input_args   jsonb NOT NULL DEFAULT '{}',
  output       text,                               -- small outputs inline
  output_artifact_id uuid,                         -- large outputs (screenshots, dumps) -> artifact
  error        text,
  started_at   timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run_started ON tool_calls (run_id, started_at);

-- ───────── Artifacts ─────────
CREATE TABLE IF NOT EXISTS artifacts (
  id             uuid PRIMARY KEY,
  workspace_id   uuid NOT NULL REFERENCES workspaces(id),
  owner_id       uuid NOT NULL REFERENCES users(id),
  session_id     uuid REFERENCES sessions(id) ON DELETE SET NULL,
  origin         text NOT NULL CHECK (origin IN ('user_upload','agent_generated','tool_output')),
  created_by_run uuid REFERENCES agent_runs(id) ON DELETE SET NULL,
  name           text NOT NULL,
  kind           text NOT NULL,                    -- 'file','image','code','report','screenshot'
  created_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz
);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts (session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_owner ON artifacts (owner_id, created_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS artifact_versions (
  id           uuid PRIMARY KEY,
  artifact_id  uuid NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  version      int  NOT NULL,
  storage_uri  text NOT NULL,                      -- s3://bucket/key or local path
  mime_type    text NOT NULL,
  size_bytes   bigint NOT NULL,
  sha256       text NOT NULL,                      -- dedupe + integrity
  metadata     jsonb NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (artifact_id, version)
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_tool_calls_output_artifact'
  ) THEN
    ALTER TABLE tool_calls ADD CONSTRAINT fk_tool_calls_output_artifact FOREIGN KEY (output_artifact_id) REFERENCES artifacts(id) ON DELETE SET NULL;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS message_artifacts (
  message_id  uuid REFERENCES messages(id) ON DELETE CASCADE,
  artifact_id uuid REFERENCES artifacts(id) ON DELETE CASCADE,
  relation    text NOT NULL DEFAULT 'attachment' CHECK (relation IN ('attachment','output','reference')),
  PRIMARY KEY (message_id, artifact_id)
);

-- ───────── Notifications ─────────
CREATE TABLE IF NOT EXISTS notifications (
  id         uuid PRIMARY KEY,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type       text NOT NULL,                        -- 'run_completed','approval_needed','agent_error'
  title      text NOT NULL,
  body       text,
  payload    jsonb NOT NULL DEFAULT '{}',          -- deep-link info: session_id, run_id...
  read_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notif_unread ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;

-- ───────── Settings (scoped KV, no migration for new settings) ─────────
CREATE TABLE IF NOT EXISTS settings (
  scope_type text NOT NULL CHECK (scope_type IN ('system','workspace','user','agent','session')),
  scope_id   text NOT NULL DEFAULT '',             -- '' for system
  key        text NOT NULL,
  value      jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (scope_type, scope_id, key)
);

-- ───────── Logs (partitioned; drop old partitions for retention) ─────────
CREATE TABLE IF NOT EXISTS logs (
  id          bigint GENERATED ALWAYS AS IDENTITY,
  ts          timestamptz NOT NULL DEFAULT now(),
  level       text NOT NULL,
  source      text NOT NULL,                       -- 'orchestrator','browser_agent','mcp:<name>'
  run_id      uuid,
  session_id  uuid,
  instance_id uuid,
  message     text NOT NULL,
  data        jsonb,
  PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

-- Default partition so logs table can accept inserts immediately
CREATE TABLE IF NOT EXISTS logs_default PARTITION OF logs DEFAULT;

CREATE INDEX IF NOT EXISTS idx_logs_run_ts ON logs (run_id, ts);
CREATE INDEX IF NOT EXISTS idx_logs_session_ts ON logs (session_id, ts);

-- ───────── Quick actions ─────────
CREATE TABLE IF NOT EXISTS quick_actions (
  id              text PRIMARY KEY,
  title           text NOT NULL,
  description     text,
  prompt          text NOT NULL,
  emoji           text,
  style           jsonb NOT NULL DEFAULT '{}',     -- replaces color_scheme
  target_agent_id text REFERENCES agent_definitions(id),
  sort_order      int NOT NULL DEFAULT 0,
  is_active       boolean NOT NULL DEFAULT true
);

-- ───────── Memory (future: requires pgvector) ─────────
-- CREATE TABLE IF NOT EXISTS memories (
--   id          uuid PRIMARY KEY,
--   user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
--   agent_id    text REFERENCES agent_definitions(id),   -- NULL = shared across agents
--   scope       text NOT NULL CHECK (scope IN ('user','agent','session')),
--   content     text NOT NULL,
--   embedding   vector(1536),
--   source_message_id uuid REFERENCES messages(id) ON DELETE SET NULL,
--   created_at  timestamptz NOT NULL DEFAULT now(),
--   expires_at  timestamptz
-- );
-- CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories USING hnsw (embedding vector_cosine_ops);
