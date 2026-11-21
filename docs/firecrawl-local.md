# Local Firecrawl with NVIDIA API

Firecrawl is self-hosted from `infra/firecrawl` (gitignored clone of github.com/firecrawl/firecrawl).
LLM features (`/extract`, JSON format) use NVIDIA NIM through its OpenAI-compatible API,
configured in `infra/firecrawl/.env`:

    OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
    OPENAI_API_KEY=<nvapi key>
    MODEL_NAME=nvidia/nemotron-3.5-lightning-30b-a3b

Setup:

    git clone --depth 1 https://github.com/firecrawl/firecrawl.git infra/firecrawl
    # create infra/firecrawl/.env as above
    cd infra/firecrawl; docker compose up -d --build

API at http://localhost:3002. Backend uses `FIRECRAWL_API_URL=http://localhost:3002` with an empty key
(`backend/mcp_servers/firecrawl.py` then runs `firecrawl-mcp` against it).
Embeddings are not configured (NVIDIA models only replace the chat model).

## Local patch
infra/firecrawl/apps/api/src/lib/generic-ai.ts forces Chat Completions when OPENAI_BASE_URL is set
(NVIDIA has no /v1/responses). Re-apply after pulling upstream; rebuild with `docker compose up -d --build api`.
