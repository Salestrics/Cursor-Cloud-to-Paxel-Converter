#!/usr/bin/env bash
# Refresh cloud-agent-transcripts-export.zip in a project repo and commit it.
#
# Shell workflow for repos that keep the export zip in git (e.g. SalestricsOS):
#   ./refresh-repo-export.sh /path/to/SalestricsOS
#   ./refresh-repo-export.sh /path/to/SalestricsOS --push
#
# If the export directory is missing but the zip exists, the zip is extracted first.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: refresh-repo-export.sh /path/to/project [options]

Refresh cloud-agent-transcripts-export.zip from the export directory and commit
it to the project git repo.

Options:
  --from-zip PATH   Unzip this file into the project export directory first
  --unzip           Unzip <project>/cloud-agent-transcripts-export.zip if export dir is missing
  --commit-msg MSG  Git commit message (default: chore: refresh cloud agent transcript export)
  --push            Push the commit to origin after committing
  --no-commit       Refresh zip only; do not git commit
  -h, --help        Show this help
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
EXPORT_DIR="$PROJECT_DIR/cloud-agent-transcripts-export"
ZIP_PATH="$PROJECT_DIR/cloud-agent-transcripts-export.zip"
FROM_ZIP=""
DO_UNZIP=0
DO_COMMIT=1
DO_PUSH=0
COMMIT_MSG="chore: refresh cloud agent transcript export"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --from-zip)
      FROM_ZIP="$2"
      shift 2
      ;;
    --unzip)
      DO_UNZIP=1
      shift
      ;;
    --commit-msg)
      COMMIT_MSG="$2"
      shift 2
      ;;
    --push)
      DO_PUSH=1
      shift
      ;;
    --no-commit)
      DO_COMMIT=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
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

unzip_into_export() {
  local archive="$1"
  if [ ! -f "$archive" ]; then
    echo "Zip not found: $archive" >&2
    exit 1
  fi
  rm -rf "$EXPORT_DIR"
  mkdir -p "$PROJECT_DIR"
  unzip -qo "$archive" -d "$PROJECT_DIR"
  if [ ! -f "$EXPORT_DIR/index.json" ]; then
    echo "Zip did not contain cloud-agent-transcripts-export/index.json" >&2
    exit 1
  fi
  echo "Extracted $archive -> $EXPORT_DIR"
}

if [ -n "$FROM_ZIP" ]; then
  unzip_into_export "$FROM_ZIP"
elif [ "$DO_UNZIP" -eq 1 ] && [ ! -f "$EXPORT_DIR/index.json" ]; then
  unzip_into_export "$ZIP_PATH"
fi

if [ ! -f "$EXPORT_DIR/index.json" ]; then
  cat >&2 <<EOF
Missing export at $EXPORT_DIR.

Provide an export directory, pass --from-zip, or place cloud-agent-transcripts-export.zip
in the project and run with --unzip.
EOF
  exit 1
fi

echo "Refreshing repo export zip..."
"$PYTHON" "$CONVERTER_DIR/merge-cloud-agent-export.py" \
  --dest "$EXPORT_DIR" \
  --zip-only

if [ "$DO_COMMIT" -eq 0 ]; then
  exit 0
fi

if ! git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $PROJECT_DIR (zip refreshed, skipping commit)" >&2
  exit 0
fi

git -C "$PROJECT_DIR" add "$ZIP_PATH"
if git -C "$PROJECT_DIR" diff --cached --quiet -- "$ZIP_PATH"; then
  echo "No zip changes to commit."
  exit 0
fi

git -C "$PROJECT_DIR" commit -m "$COMMIT_MSG"
echo "Committed $ZIP_PATH"

if [ "$DO_PUSH" -eq 1 ]; then
  git -C "$PROJECT_DIR" push
  echo "Pushed export zip to origin."
fi
