# ==============================================================================
# Multi-Agent Orchestrator - Backend Dockerfile
# Python 3.12 + Node.js 20 (for Playwright MCP) + Headless Chromium
# ==============================================================================
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    BROWSER_MODE=headless \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 1. Install system utilities and Node.js (LTS v20) for Playwright MCP server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    git \
    build-essential \
    ca-certificates \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 3. Install Playwright browser and system OS dependencies for headless automation
RUN playwright install --with-deps chromium \
    && npm install -g @playwright/mcp@latest

# 4. Copy backend source code and assets
COPY backend/server.py ./
COPY infra/db/schema.sql docs/database_schema.md ./
COPY backend/app ./app
COPY backend/db ./db

COPY backend/adk_agents ./adk_agents
COPY backend/config ./config
COPY backend/mcp_servers ./mcp_servers
COPY backend/tools ./tools
COPY backend/skills ./skills

# Ensure directory for browser profile persistence exists
RUN mkdir -p /app/data/browser_profiles

EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
