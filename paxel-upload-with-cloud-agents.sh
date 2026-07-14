#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 /path/to/project [--since 2m]" >&2
  exit 1
fi

PROJECT_DIR="$1"
shift

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

CONVERTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${EXPORT_DIR:-}" ]; then
  :
elif [ -d "$PROJECT_DIR/cloud-agent-transcripts-export" ]; then
  EXPORT_DIR="$PROJECT_DIR/cloud-agent-transcripts-export"
else
  EXPORT_DIR="$CONVERTER_DIR/cloud-agent-transcripts-export"
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "python3 or python is required" >&2
  exit 1
fi

OUTPUT_DIR="${PAXEL_CLOUD_AGENT_CURSOR_DIR:-$HOME/.paxel/cloud-agent-cursor-staging}"

echo "Converting Cursor Cloud Agent transcripts..."
echo "  export dir: $EXPORT_DIR"
echo "  workspace:  $PROJECT_DIR"
echo "  staging:    $OUTPUT_DIR"

"$PYTHON" "$CONVERTER_DIR/convert-cloud-agent-transcripts-to-paxel.py" \
  --export-dir "$EXPORT_DIR" \
  --output-dir "$OUTPUT_DIR" \
  --workspace "$PROJECT_DIR"

PATCHED_UPLOAD="$(mktemp "${TMPDIR:-/tmp}/paxel-upload-cloud-agents.XXXXXX.sh")"
trap 'rm -f "$PATCHED_UPLOAD"' EXIT

curl -fsSL 'https://paxel.ycombinator.com/upload.sh' -o "$PATCHED_UPLOAD"
"$PYTHON" "$CONVERTER_DIR/patch-paxel-for-cloud-agents.py" "$PATCHED_UPLOAD"

export PAXEL_CLOUD_AGENT_CURSOR_DIR="$OUTPUT_DIR"

if [ -z "${YC_TOKEN:-}" ]; then
  echo "Warning: YC_TOKEN is not set. Paxel sign-in may still work via browser auth." >&2
fi

(
  cd "$PROJECT_DIR"
  bash "$PATCHED_UPLOAD" "$@"
)
