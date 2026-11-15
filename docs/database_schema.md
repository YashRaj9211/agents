# Multi-Agent Orchestrator - Enterprise Database Architecture

## Architecture Overview

This database architecture is designed for an enterprise-ready **Multi-Agent Orchestrator Platform** running on **PostgreSQL**. It moves the system away from volatile in-memory sessions to persistent, auditable, multi-tenant execution traces.

### Domain & Tables

| Domain | Tables | Description |
|---|---|---|
| **Identity** | `users`, `workspaces`, `workspace_members` | Multi-tenant identity, workspace role-based access control (RBAC). |
| **Catalog** | `agent_definitions`, `tools`, `mcp_servers`, `agent_tools`, `credentials`, `browser_profiles`, `quick_actions` | Agent registry, MCP servers, tool catalog, encrypted secrets, and browser environments. |
| **Fleet** | `agent_instances` | Distributed worker nodes, heartbeat monitoring, and fleet status. |
| **Conversation** | `sessions`, `messages` | Chat sessions with strictly ordered messages (`seq`), sidebar indexing. |
| **Execution** | `agent_runs`, `tool_calls` | Hierarchical execution trees (`parent_run_id`), live tool invocations and output capture. |
| **Files** | `artifacts`, `artifact_versions`, `message_artifacts` | Object-stored artifacts (reports, screenshots, code files, downloads) with SHA256 integrity and versioning. |
| **Platform** | `notifications`, `settings`, `logs` | Scoped hierarchical settings (session > user > agent > workspace > system), partitioned logs, user notifications. |
| **Later** | `memories` | Long-term vector memory embeddings via `pgvector` (HNSW cosine similarity). |

---

## Entity Relationship & Schema Details

### 1. Identity & Multi-Tenancy
* **`users`**: Uses application-generated UUIDv7 (time-ordered sequential UUIDs) and `citext` for case-insensitive unique usernames. Maps to OAuth identity providers (`auth_provider`, `auth_subject`).
* **`workspaces`**: Logical boundary for team collaboration and multi-tenancy.
* **`workspace_members`**: Join table enforcing roles (`owner`, `admin`, `member`, `viewer`).

### 2. Catalog & Fleet
* **`agent_definitions`**: Catalog of AI agents (e.g. `root_agent`, `browser_agent`, `cli_agent`, `scheduler_agent`). Stores model parameters, system prompts, and configuration in `jsonb`.
* **`tools`**: Built-in and MCP-provided tools with JSON Schema input schemas. Enforces PG15+ `UNIQUE NULLS NOT DISTINCT (mcp_server_id, name)`.
* **`mcp_servers`**: Configuration for stdio, sse, and http MCP servers, linked to encrypted credentials.
* **`agent_tools`**: Granular capability permissions determining which agent can execute which tool.
* **`credentials`**: KMS/Fernet-encrypted secrets for MCPs, API keys, and external authentication.
* **`agent_instances`**: Tracks worker fleet processes, host machines, heartbeats, and lifecycle states (`idle`, `busy`, `draining`, `offline`).

### 3. Conversations & Execution Trees
* **`sessions`**: Thread grouping with `user_id`, `primary_agent_id`, and partial index `sessions_sidebar` (`(user_id, last_message_at DESC) WHERE deleted_at IS NULL`).
* **`messages`**: Ordered via monotonically increasing `seq` per session. Mutually exclusive foreign key between `sender_user_id` and `sender_agent_id`. Linked to `agent_runs`.
* **`agent_runs`**: Represents an agent invocation. Supports nested handoff trees through self-referential `parent_run_id` (e.g., `root_agent` delegating to `browser_agent`). Captures token usage, latency, and status.
* **`tool_calls`**: Records tool invocations tied to an `agent_run`. Includes argument snapshots, execution timing, inline text output, or references to binary/large artifacts in `artifacts`.

### 4. Files & Artifacts
* **`artifacts`**: Metadata for generated screenshots, code files, or data dumps.
* **`artifact_versions`**: Versioned pointers to S3/MinIO storage with SHA256 deduplication and mime types.
* **`message_artifacts`**: Links chat messages with artifacts (`attachment`, `output`, `reference`).

### 5. Platform Infrastructure
* **`settings`**: Scoped key-value configuration (`scope_type`: `system`, `workspace`, `user`, `agent`, `session`). Precedence resolution: `session > user > agent > workspace > system`.
* **`logs`**: High-throughput audit logging partitioned by timestamp (`PARTITION BY RANGE (ts)`), enabling effortless log retention pruning.
* **`notifications`**: Targeted user alerts for long-running task completions, approval requests, and agent errors.
* **`quick_actions`**: User-facing prompt shortcuts and workflow templates.

---

## Design Principles

1. **UUIDv7 Primary Keys**: Sequential, timestamp-prefixed UUIDs prevent B-Tree index fragmentation and enable natural chronological sorting without extra indexes.
2. **Handoff Run Tree**: Eliminates the need to serialize sub-agent coordination state into message text. The UI timeline queries `agent_runs` and `tool_calls` ordered by `started_at`.
3. **Advisory Lock & Strict Ordering**: Message sequence `seq` is allocated within an insert transaction using `max(seq) + 1` or session advisory locks to prevent race conditions during streaming.
4. **Tool Snapshotting**: `tool_calls.tool_name` is stored as an immutable string, guaranteeing that historical logs remain intact even if an MCP server or tool is removed.
5. **Decoupled Heavy Storage**: Large outputs (DOM snapshots, full-page screenshots) are offloaded to object storage through `artifacts` and linked via `output_artifact_id`.

---

## Suggested Implementation Roadmap

1. **Phase 1: Core Execution & Chat Persistence (Priority)**
   - Tables: `users`, `agent_definitions`, `sessions`, `messages`, `agent_runs`, `tool_calls`.
   - Goal: Replace the in-memory runner (`InMemoryRunner`) with persistent Postgres session/run management and timeline queries.
2. **Phase 2: Storage & Platform Configuration**
   - Tables: `artifacts`, `artifact_versions`, `message_artifacts`, `notifications`, `settings`.
   - Goal: File uploads, browser screenshot persistence, and user/agent setting overrides.
3. **Phase 3: Dynamic MCP & Catalog Management**
   - Tables: `tools`, `mcp_servers`, `credentials`, `agent_tools`, `browser_profiles`.
   - Goal: Dynamic tool attachment, credential management, and isolated browser profile management.
4. **Phase 4: Distributed Fleet & Telemetry**
   - Tables: `agent_instances`, `logs` (with partitioned rotation).
   - Goal: Multi-worker node orchestration and enterprise audit trails.
5. **Phase 5: Long-Term Memory**
   - Tables: `memories` (with `pgvector` HNSW indexes).
   - Goal: Semantic cross-session recall and agent memory retrieval.
