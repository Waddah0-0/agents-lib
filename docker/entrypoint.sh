#!/bin/sh
# Container start-up. On the first start, point margin at the model server named by
# MARGIN_SEED_LOCAL_LLM_BASE_URL (compose.yaml sets it to the host's Ollama). It is saved like
# a choice made on the Settings page, so the UI can still change it later.
set -e
if [ -n "${MARGIN_SEED_LOCAL_LLM_BASE_URL:-}" ]; then
  python - <<'PY'
import os
from margin_core.config import load_user_config, save_user_config

if "local_llm_base_url" not in load_user_config():
    save_user_config({"local_llm_base_url": os.environ["MARGIN_SEED_LOCAL_LLM_BASE_URL"]})
PY
fi
exec "$@"
