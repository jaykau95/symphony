#!/usr/bin/env bash
# Symphony container entrypoint.
# Writes Codex auth from environment, then starts the orchestrator.

set -euo pipefail

# ── Codex authentication ────────────────────────────────────────────────────
# Codex reads ~/.codex/auth.json.  We write it from OPENAI_API_KEY so the
# key never has to be baked into the image.
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    mkdir -p ~/.codex
    printf '{"apiKey":"%s"}\n' "$OPENAI_API_KEY" > ~/.codex/auth.json
    echo "Codex auth configured from OPENAI_API_KEY"
else
    echo "WARNING: OPENAI_API_KEY is not set — Codex sessions will likely fail"
fi

# ── SSH key for git clone in hooks (optional) ───────────────────────────────
# Set GIT_SSH_PRIVATE_KEY to a base64-encoded private key string.
if [[ -n "${GIT_SSH_PRIVATE_KEY:-}" ]]; then
    mkdir -p ~/.ssh
    echo "$GIT_SSH_PRIVATE_KEY" | base64 -d > ~/.ssh/id_rsa
    chmod 600 ~/.ssh/id_rsa
    ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
    echo "Git SSH key configured"
fi

# ── Start Symphony ───────────────────────────────────────────────────────────
WORKFLOW="${WORKFLOW_PATH:-/app/WORKFLOW.md}"
echo "Starting Symphony with workflow: $WORKFLOW"

exec python3 -m symphony.main "$WORKFLOW" \
    --logs-root "${LOGS_ROOT:-/app/log}" \
    --log-level "${LOG_LEVEL:-INFO}"
