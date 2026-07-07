#!/bin/sh
set -e

# ─────────────────────────────────────────────────────────────────────────
# Runtime injection of NEXT_PUBLIC_API_BASE_URL.
#
# Next.js inlines NEXT_PUBLIC_* into the compiled bundle at BUILD time, so it
# can't normally be changed without rebuilding. To make this image runtime-
# configurable, we build with a sentinel string and swap it for the real value
# here, on container start. Result: set NEXT_PUBLIC_API_BASE_URL in your
# platform's env vars and just restart — no rebuild, no build args.
#
# A marker file records the value last injected, so this is correct even when
# the SAME container is restarted with a *changed* URL (we replace the previous
# value, not just the original sentinel). On a fresh container the marker is
# absent and we replace the build-time sentinel.
# ─────────────────────────────────────────────────────────────────────────

: "${NEXT_PUBLIC_API_BASE_URL:=http://localhost:8000/api/v1}"

SENTINEL="APP_RUNTIME_API_BASE_URL"
MARKER="/app/.next/.api_base_injected"
TARGET="$NEXT_PUBLIC_API_BASE_URL"

CURRENT="$SENTINEL"
[ -f "$MARKER" ] && CURRENT="$(cat "$MARKER")"

if [ "$TARGET" != "$CURRENT" ]; then
  echo "[entrypoint] setting API base URL: ${TARGET}"
  # '|' as the sed delimiter so the URL's slashes don't need escaping.
  find /app/.next -type f \( -name "*.js" -o -name "*.json" -o -name "*.html" \) \
    -exec sed -i "s|${CURRENT}|${TARGET}|g" {} + 2>/dev/null || true
  echo "$TARGET" > "$MARKER" 2>/dev/null || true
fi

exec "$@"
