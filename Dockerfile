# Symphony — Railway deployment image
# Installs Python deps + Codex CLI, then runs the Python orchestrator.

FROM python:3.12-slim

# Node.js is required for the Codex CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nodejs npm git curl bash openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally
RUN npm install -g @openai/codex

WORKDIR /app

# Python dependencies
COPY python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY python/ ./

# WORKFLOW.md used by the Python orchestrator
COPY python/WORKFLOW.railway.md ./WORKFLOW.md

# Startup script (writes Codex auth + launches Symphony)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Workspace directory — mount a Railway Volume here for persistence
RUN mkdir -p /workspaces

ENTRYPOINT ["/docker-entrypoint.sh"]
