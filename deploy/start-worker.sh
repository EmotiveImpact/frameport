#!/usr/bin/env bash
set -euo pipefail
export FRAMEPORT_DATA="${FRAMEPORT_DATA:-/data}"
export FRAMEPORT_PUBLIC_ORIGIN="${FRAMEPORT_PUBLIC_ORIGIN:-https://frameport.vercel.app}"
FRAMEPORT_API_KEY="${FRAMEPORT_API_KEY:-}"
export FRAMEPORT_API_KEY
if [[ ${#FRAMEPORT_API_KEY} -lt 24 ]]; then
  echo 'Set FRAMEPORT_API_KEY to at least 24 random characters before deploying.' >&2; exit 1
fi
if [[ "${FRAMEPORT_UNSANDBOXED_TEST_BROWSER:-0}" == "1" ]]; then
  echo 'The hosted worker refuses the unsandboxed test flag.' >&2; exit 1
fi
if [[ ! -d "$FRAMEPORT_DATA" ]]; then mkdir -p "$FRAMEPORT_DATA"; fi
# Railway volumes mount root-owned. Drop privileges before launching the API or Chromium.
if [[ "$(id -u)" == "0" ]]; then
  chown -R pwuser:pwuser "$FRAMEPORT_DATA"
  exec runuser -u pwuser -- python -m frameport.cli --host 0.0.0.0 --port "${PORT:-8040}"
fi
exec python -m frameport.cli --host 0.0.0.0 --port "${PORT:-8040}"
