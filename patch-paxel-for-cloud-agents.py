#!/usr/bin/env python3
"""Patch Paxel upload.sh in place to support Cursor Cloud Agent JSONL staging."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PATCHES: list[tuple[str, str, str]] = [
    (
        "collect_cursor_sessions cloud staging import",
        """collect_cursor_sessions() {
  local tmpdir="$1"
  local selected_remote="${2:-}"

  # Dependency check""",
        """collect_cursor_sessions() {
  local tmpdir="$1"
  local selected_remote="${2:-}"

  # Cloud Agent staging import (Cursor Cloud → Paxel bridge)
  if [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ]; then
    local cloud_count=0
    for bucket in "$PAXEL_CLOUD_AGENT_CURSOR_DIR"/_cursor_*/; do
      [ -d "$bucket" ] || continue
      local bucket_name
      bucket_name=$(basename "$bucket")
      mkdir -p "$tmpdir/$bucket_name"
      cp -f "$bucket"/*.jsonl "$tmpdir/$bucket_name/" 2>/dev/null || true
      cloud_count=$((cloud_count + $(find "$tmpdir/$bucket_name" -name "*.jsonl" 2>/dev/null | wc -l | tr -d ' ')))
    done
    if [ -f "$PAXEL_CLOUD_AGENT_CURSOR_DIR/_metadata.json" ]; then
      cp -f "$PAXEL_CLOUD_AGENT_CURSOR_DIR/_metadata.json" "$tmpdir/_metadata.json"
    fi
    if [ "$cloud_count" -gt 0 ]; then
      echo "  Cursor Cloud Agent: ${cloud_count} sessions imported from staging" >&2
      return 0
    fi
  fi

  # Dependency check""",
    ),
    (
        "session_count includes cloud staging imports (project picker)",
        """local session_count=$((claude_count + codex_main_count))
  # If no Claude/Codex sessions, fold in opencode/Gemini""",
        """local cursor_import_count=0
  if [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ]; then
    cursor_import_count=$(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -maxdepth 2 -path "*/_cursor_*/*.jsonl" 2>/dev/null | wc -l | tr -d ' ')
  fi
  local session_count=$((claude_count + codex_main_count + cursor_import_count))
  # If no Claude/Codex sessions, fold in opencode/Gemini""",
    ),
    (
        "session_count includes cloud staging imports (single-repo)",
        """local session_count=$((claude_count + codex_standalone_count + opencode_count + gemini_count + vscode_count))

  if [ "$session_count" -eq 0 ]; then""",
        """local cursor_import_count=0
  if [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ]; then
    cursor_import_count=$(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -maxdepth 2 -path "*/_cursor_*/*.jsonl" 2>/dev/null | wc -l | tr -d ' ')
  fi
  local session_count=$((claude_count + codex_standalone_count + opencode_count + gemini_count + vscode_count + cursor_import_count))

  if [ "$session_count" -eq 0 ]; then""",
    ),
    (
        "auto-detect cloud staging without none-match prompt",
        """elif [ -n "$cwd_remote" ] && remote_has_agent_sessions "$cwd_remote"; then""",
        """elif [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ] \\
      && [ -n "$(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -maxdepth 2 -path '*/_cursor_*/*.jsonl' -print -quit 2>/dev/null)" ]; then
      CLAUDE_DIR="$filtered_dir"
      CLAUDE_MOUNT_SCOPE="filtered"
      MOUNT_LABEL="$match_label"
      selected_remote="$cwd_remote"
      if command -v jq >/dev/null 2>&1; then
        echo '{"version": 1, "directories": {}}' > "${filtered_dir}/_metadata.json"
      fi
      echo "Auto-detected project: ${match_label} (matched Cursor Cloud Agent staging; no Claude Code history here)" >&2
    elif [ -n "$cwd_remote" ] && remote_has_agent_sessions "$cwd_remote"; then""",
    ),
    (
        "maybe_prescan_cursor_remotes allows cloud staging without local Cursor DB",
        """  command -v sqlite3 >/dev/null 2>&1 || return 0
  command -v jq >/dev/null 2>&1 || return 0
  [ -d "${CURSOR_DIR:-}" ] || [ -f "${CURSOR_GLOBAL_DB:-}" ] || return 0""",
        """  if [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ]; then
    local set="|" f r rn
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      if command -v jq >/dev/null 2>&1; then
        r=$(head -1 "$f" | jq -r '._cursor_meta.git_remote // empty' 2>/dev/null || true)
      else
        r=""
      fi
      [ -z "$r" ] && continue
      rn=$(normalize_remote "$r")
      [ -z "$rn" ] && continue
      case "$set" in *"|${rn}|"*) ;; *) set="${set}${rn}|" ;; esac
    done < <(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -path '*/_cursor_*/*.jsonl' 2>/dev/null)
    _PAXEL_CURSOR_REMOTES="$set"
    return 0
  fi
  command -v sqlite3 >/dev/null 2>&1 || return 0
  command -v jq >/dev/null 2>&1 || return 0
  [ -d "${CURSOR_DIR:-}" ] || [ -f "${CURSOR_GLOBAL_DB:-}" ] || return 0""",
    ),
    (
        "inject _paxel_should_run_cursor_extraction helper",
        """run_docker_analysis() {""",
        """_paxel_should_run_cursor_extraction() {
  if [ -n "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] && [ -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ]; then
    [ -n "$(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -maxdepth 2 -path '*/_cursor_*/*.jsonl' -print -quit 2>/dev/null)" ] && return 0
  fi
  { [ -d "$CURSOR_DIR" ] || [ -f "$CURSOR_GLOBAL_DB" ]; } && command -v sqlite3 &>/dev/null && command -v jq &>/dev/null
}

run_docker_analysis() {""",
    ),
    (
        "docker cursor mount gate uses helper",
        """if { [ -d "$CURSOR_DIR" ] || [ -f "$CURSOR_GLOBAL_DB" ]; } && command -v sqlite3 &>/dev/null && command -v jq &>/dev/null; then""",
        """if _paxel_should_run_cursor_extraction; then""",
    ),
    (
        "missing-tools hint only when not using cloud staging",
        """  if { [ -d "$CURSOR_DIR" ] || [ -f "$CURSOR_GLOBAL_DB" ]; } \\
     && { ! command -v sqlite3 >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; }; then""",
        """  if { [ -d "$CURSOR_DIR" ] || [ -f "$CURSOR_GLOBAL_DB" ]; } \\
     && { ! command -v sqlite3 >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; } \\
     && { [ -z "${PAXEL_CLOUD_AGENT_CURSOR_DIR:-}" ] || [ ! -d "$PAXEL_CLOUD_AGENT_CURSOR_DIR" ] || [ -z "$(find "$PAXEL_CLOUD_AGENT_CURSOR_DIR" -maxdepth 2 -path '*/_cursor_*/*.jsonl' -print -quit 2>/dev/null)" ]; }; then""",
    ),
]


def patch_upload_script(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    applied: list[str] = []

    for label, old, new in PATCHES:
        if old not in text:
            raise ValueError(f"Patch anchor not found for {label}")
        if new in text:
            applied.append(f"skip (already applied): {label}")
            continue
        text = text.replace(old, new, 1)
        applied.append(label)

    path.write_text(text, encoding="utf-8")
    return applied


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch Paxel upload.sh for Cursor Cloud Agent imports.")
    parser.add_argument("upload_script", help="Path to downloaded Paxel upload.sh")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    upload_script = Path(args.upload_script).expanduser().resolve()

    if not upload_script.is_file():
        print(f"Upload script not found: {upload_script}", file=sys.stderr)
        return 1

    try:
        applied = patch_upload_script(upload_script)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for label in applied:
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
