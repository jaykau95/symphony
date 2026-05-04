#!/usr/bin/env bash
# Symphony container entrypoint.
# Writes Codex auth from environment, then starts the orchestrator.
#
# Auth modes (in priority order):
#
#   1. CODEX_AUTH_JSON  — base64-encoded contents of ~/.codex/auth.json
#                         Use this for Codex OAuth credits (recommended).
#                         Get it by running: base64 -w0 ~/.codex/auth.json
#
#   2. OPENAI_API_KEY   — standard OpenAI API key (sk-...)
#                         Uses API credits, not Codex subscription credits.

set -euo pipefail

mkdir -p ~/.codex

# ── Codex authentication ────────────────────────────────────────────────────

if [[ -n "${CODEX_AUTH_JSON:-}" ]]; then
    # Mode 1: OAuth / Codex credits — full auth.json supplied as base64
    echo "$CODEX_AUTH_JSON" | base64 -d > ~/.codex/auth.json
    echo "Codex auth configured from CODEX_AUTH_JSON (OAuth / Codex credits)"

elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
    # Mode 2: API key — uses OpenAI API credits
    printf '{"apiKey":"%s"}\n' "$OPENAI_API_KEY" > ~/.codex/auth.json
    echo "Codex auth configured from OPENAI_API_KEY (API credits)"

else
    echo "WARNING: Neither CODEX_AUTH_JSON nor OPENAI_API_KEY is set — Codex sessions will fail"
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
    --port "${PORT:-8080}" \
    --logs-root "${LOGS_ROOT:-/app/log}" \
    --log-level "${LOG_LEVEL:-INFO}"
