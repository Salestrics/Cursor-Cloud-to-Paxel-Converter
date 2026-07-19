#!/usr/bin/env bash
# One-command automation for the Cursor Cloud → Paxel bridge.
#
# Typical agent workflow:
#   1. list-cloud-agents (paginate; filter with did_make_code_changes when useful)
#   2. batch-fetch-details with include_transcripts: true (max 50 bc_ids per call)
#   3. ./automate-bridge.sh /path/to/project
#
# The script auto-detects the latest MCP export under /tmp/cursor/cloud-agent-transcripts
# unless you pass --sync-from or set MCP_EXPORT_DIR.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: automate-bridge.sh /path/to/project [options] [-- upload-args...]

Automates the Cursor Cloud → Paxel bridge:
  1. Merge MCP batch-fetch export into <project>/cloud-agent-transcripts-export
  2. Convert transcripts to Paxel staging JSONL
  3. Download, patch, and run Paxel upload.sh

Options:
  --sync-from DIR   MCP export directory to merge (default: latest /tmp export or MCP_EXPORT_DIR)
  --no-sync         Skip MCP export merge; use the existing project export only
  --sync-only       Merge MCP export and exit (no Paxel upload)
  --force-sync      Overwrite agents that already exist in the project export
  --zip             Refresh cloud-agent-transcripts-export.zip after merge or before upload
  --commit-export   Git commit the refreshed zip in the project repo
  --push-export     Push after --commit-export
  --since DURATION  Paxel upload window (default: 2m)
  -h, --help        Show this help

Environment:
  MCP_EXPORT_DIR    Default --sync-from directory when set
  EXPORT_DIR        Override project export directory
  YC_TOKEN          Optional Paxel API token
EOF
}

if [ "$#" -lt 1 ]; then
  usage >&2
  exit 1
fi

PROJECT_DIR="$1"
shift

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

CONVERTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORT_DIR="${EXPORT_DIR:-$PROJECT_DIR/cloud-agent-transcripts-export}"
SYNC_FROM="${MCP_EXPORT_DIR:-}"
DO_SYNC=1
SYNC_ONLY=0
FORCE_SYNC=0
MAKE_ZIP=0
COMMIT_EXPORT=0
PUSH_EXPORT=0
SINCE="2m"
UPLOAD_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sync-from)
      SYNC_FROM="$2"
      shift 2
      ;;
    --no-sync)
      DO_SYNC=0
      shift
      ;;
    --sync-only)
      SYNC_ONLY=1
      shift
      ;;
    --force-sync)
      FORCE_SYNC=1
      shift
      ;;
    --zip)
      MAKE_ZIP=1
      shift
      ;;
    --commit-export)
      COMMIT_EXPORT=1
      MAKE_ZIP=1
      shift
      ;;
    --push-export)
      PUSH_EXPORT=1
      COMMIT_EXPORT=1
      MAKE_ZIP=1
      shift
      ;;
    --since)
      SINCE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      UPLOAD_ARGS+=("$@")
      break
      ;;
    *)
      UPLOAD_ARGS+=("$1")
      shift
      ;;
  esac
done

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "python3 or python is required" >&2
  exit 1
fi

MERGE_ARGS=()
if [ -n "$SYNC_FROM" ]; then
  MERGE_ARGS+=(--source "$SYNC_FROM")
fi
if [ "$FORCE_SYNC" -eq 1 ]; then
  MERGE_ARGS+=(--force)
fi
if [ "$MAKE_ZIP" -eq 1 ]; then
  MERGE_ARGS+=(--zip)
fi

if [ "$DO_SYNC" -eq 1 ]; then
  echo "Syncing Cursor Cloud MCP export into project export..."
  echo "  source: ${SYNC_FROM:-<latest /tmp/cursor/cloud-agent-transcripts>}"
  echo "  dest:   $EXPORT_DIR"
  if ! "$PYTHON" "$CONVERTER_DIR/merge-cloud-agent-export.py" \
    --dest "$EXPORT_DIR" \
    "${MERGE_ARGS[@]}"; then
    if [ ! -f "$EXPORT_DIR/index.json" ]; then
      echo "No export available yet. Run batch-fetch-details with include_transcripts: true first." >&2
      exit 1
    fi
    echo "Warning: MCP sync skipped or found nothing new; continuing with existing export." >&2
  fi
fi

if [ "$SYNC_ONLY" -eq 1 ]; then
  if [ "$MAKE_ZIP" -eq 1 ] && [ "$DO_SYNC" -eq 0 ]; then
    "$PYTHON" "$CONVERTER_DIR/merge-cloud-agent-export.py" \
      --dest "$EXPORT_DIR" \
      --zip-only
  fi
  if [ "$COMMIT_EXPORT" -eq 1 ]; then
    COMMIT_ARGS=("$PROJECT_DIR")
    [ "$PUSH_EXPORT" -eq 1 ] && COMMIT_ARGS+=(--push)
    "$CONVERTER_DIR/refresh-repo-export.sh" "${COMMIT_ARGS[@]}"
  fi
  exit 0
fi

if [ ! -f "$EXPORT_DIR/index.json" ]; then
  cat >&2 <<EOF
Missing export at $EXPORT_DIR.

Run this from a Cursor Agent with Cloud MCP access:
  1. list-cloud-agents
  2. batch-fetch-details with include_transcripts: true
  3. ./automate-bridge.sh "$PROJECT_DIR"
EOF
  exit 1
fi

if [ "$MAKE_ZIP" -eq 1 ] && [ "$DO_SYNC" -eq 0 ]; then
  "$PYTHON" "$CONVERTER_DIR/merge-cloud-agent-export.py" \
    --dest "$EXPORT_DIR" \
    --zip-only
fi

if [ "$COMMIT_EXPORT" -eq 1 ]; then
  COMMIT_ARGS=("$PROJECT_DIR")
  [ "$PUSH_EXPORT" -eq 1 ] && COMMIT_ARGS+=(--push)
  "$CONVERTER_DIR/refresh-repo-export.sh" "${COMMIT_ARGS[@]}"
fi

export EXPORT_DIR
exec "$CONVERTER_DIR/paxel-upload-with-cloud-agents.sh" "$PROJECT_DIR" --since "$SINCE" "${UPLOAD_ARGS[@]}"
