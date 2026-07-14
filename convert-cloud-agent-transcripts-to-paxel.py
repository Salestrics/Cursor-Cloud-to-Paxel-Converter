#!/usr/bin/env python3
"""Convert Cursor Cloud Agent transcript exports to Paxel Cursor JSONL format."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_NAME_MAP = {
    "run_terminal_cmd": "Bash",
    "run_terminal_command_v2": "Bash",
    "Shell": "Bash",
    "read": "Read",
    "Read": "Read",
    "read_file": "Read",
    "read_file_v2": "Read",
    "write": "Edit",
    "StrReplace": "Edit",
    "Edit": "Edit",
    "edit_file": "Edit",
    "edit_file_v2": "Edit",
    "search_replace": "Edit",
    "Grep": "Grep",
    "grep": "Grep",
    "ripgrep_raw_search": "Grep",
    "Glob": "Glob",
    "glob_file_search": "Glob",
    "glob_file_search_v2": "Glob",
    "Task": "Task",
    "task_v2": "Task",
}

DEFAULT_EXPORT_DIR = "cloud-agent-transcripts-export"
DEFAULT_OUTPUT_DIR = Path.home() / ".paxel" / "cloud-agent-cursor-staging"


def stable_hash6(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:6]


def normalize_git_remote(remote: str) -> str:
    remote = remote.strip()
    if not remote:
        return ""

    ssh_match = re.match(r"^git@([^:]+):(.+)$", remote)
    if ssh_match:
        host, path = ssh_match.groups()
        remote = f"https://{host}/{path}"

    remote = re.sub(r"\.git$", "", remote, flags=re.IGNORECASE)
    return remote


def resolve_git_remote(workspace: Path, git_remote: str | None) -> str:
    if git_remote:
        return normalize_git_remote(git_remote)

    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""

    return normalize_git_remote(result.stdout.strip())


def ms_to_iso(timestamp_ms: int | float | None) -> str:
    if not timestamp_ms:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (OSError, OverflowError, ValueError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canon_tool_name(name: str | None) -> str:
    if not name:
        return "tool"
    return TOOL_NAME_MAP.get(name, name)


def remap_tool_input(tool_name: str, tool_args: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(tool_args or {})
    if tool_name == "Read":
        if "target_file" in payload and "file_path" not in payload:
            payload["file_path"] = payload.pop("target_file")
        if "path" in payload and "file_path" not in payload:
            payload["file_path"] = payload.pop("path")
    elif tool_name == "Edit":
        if "relativeWorkspacePath" in payload and "file_path" not in payload:
            payload["file_path"] = payload.pop("relativeWorkspacePath")
        if "target_file" in payload and "file_path" not in payload:
            payload["file_path"] = payload.pop("target_file")
    elif tool_name == "Bash":
        if "command" in payload and "cmd" not in payload:
            payload["cmd"] = payload["command"]
    return payload


def extract_tool_result_text(tool_result: Any) -> str:
    if tool_result is None:
        return ""

    if isinstance(tool_result, str):
        return tool_result[:4000]

    if isinstance(tool_result, dict):
        value = tool_result.get("value")
        if isinstance(value, dict):
            for key in ("output", "contents", "result", "text", "content"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate:
                    return candidate[:4000]
        for key in ("output", "contents", "result", "text", "content"):
            candidate = tool_result.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate[:4000]

    try:
        return json.dumps(tool_result, ensure_ascii=False)[:4000]
    except TypeError:
        return str(tool_result)[:4000]


def make_user_line(text: str, timestamp: str) -> dict[str, Any]:
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": timestamp,
    }


def make_assistant_line(
    text: str | None,
    thinking: str | None,
    tool_calls: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, Any] | None:
    content: list[dict[str, Any]] = []
    if thinking:
        content.append({"type": "thinking", "thinking": thinking})
    if text:
        content.append({"type": "text", "text": text})
    for tool_call in tool_calls:
        tool_name = canon_tool_name(tool_call.get("tool_name"))
        tool_args = tool_call.get("tool_args") or {}
        entry: dict[str, Any] = {
            "type": "tool_use",
            "name": tool_name,
            "input": remap_tool_input(tool_name, tool_args),
        }
        tool_call_id = tool_call.get("tool_call_id")
        if tool_call_id:
            entry["id"] = tool_call_id
        content.append(entry)

    if not content:
        return None

    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": content},
        "timestamp": timestamp,
    }


def make_tool_result_line(
    tool_call_id: str | None,
    tool_result: Any,
    timestamp: str,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "tool_result",
        "content": extract_tool_result_text(tool_result),
    }
    if tool_call_id:
        entry["tool_use_id"] = tool_call_id
    return {
        "type": "user",
        "message": {"role": "user", "content": [entry]},
        "timestamp": timestamp,
    }


def convert_transcript(
    transcript: dict[str, Any],
    *,
    composer_id: str,
    workspace: str,
    git_remote: str,
    cloud_agent_name: str,
) -> list[dict[str, Any]]:
    messages = transcript.get("messages", [])
    lines: list[dict[str, Any]] = []

    for message in messages:
        role = message.get("role")
        timestamp = ms_to_iso(
            message.get("started_at_ms")
            or message.get("completed_at_ms")
            or message.get("created_at_ms")
        )

        if role == "user":
            text = message.get("text") or message.get("content") or ""
            if isinstance(text, list):
                text = " ".join(
                    part.get("text", "")
                    for part in text
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if text:
                lines.append(make_user_line(str(text), timestamp))
            continue

        if role == "assistant":
            assistant_line = make_assistant_line(
                message.get("text"),
                message.get("thinking"),
                message.get("tool_calls") or [],
                timestamp,
            )
            if assistant_line:
                lines.append(assistant_line)
            continue

        if role == "tool":
            lines.append(
                make_tool_result_line(
                    message.get("tool_call_id"),
                    message.get("tool_result"),
                    timestamp,
                )
            )

    if not lines:
        return []

    meta = {
        "composerId": composer_id,
        "workspace": workspace,
        "git_remote": git_remote,
        "agent_type": "cursor",
        "cloud_agent_name": cloud_agent_name,
    }
    lines[0] = {**lines[0], "_cursor_meta": meta}
    return lines


def clear_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def load_index(export_dir: Path) -> list[dict[str, Any]]:
    index_path = export_dir / "index.json"
    if not index_path.is_file():
        raise FileNotFoundError(f"Missing index file: {index_path}")

    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    agents = payload.get("agents", [])
    if not agents:
        raise ValueError(f"No agents listed in {index_path}")
    return agents


def transcript_path_for_agent(export_dir: Path, bc_id: str) -> Path:
    candidates = [
        export_dir / bc_id / "transcript.json",
        export_dir / f"bc-{bc_id.removeprefix('bc-')}" / "transcript.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing transcript for {bc_id} in {export_dir}")


def convert_exports(
    export_dir: Path,
    output_dir: Path,
    workspace: Path,
    git_remote: str | None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    resolved_remote = resolve_git_remote(workspace, git_remote)
    project_name = workspace.name or "project"
    bucket_name = f"_cursor_{project_name}_{stable_hash6(str(workspace))}"
    bucket_dir = output_dir / bucket_name

    clear_output_dir(output_dir)
    bucket_dir.mkdir(parents=True, exist_ok=True)

    manifest_sessions: list[dict[str, Any]] = []
    converted = 0

    for agent in load_index(export_dir):
        bc_id = agent.get("bcId")
        if not bc_id:
            continue

        transcript_path = transcript_path_for_agent(export_dir, bc_id)
        with transcript_path.open("r", encoding="utf-8") as handle:
            transcript = json.load(handle)

        cloud_agent_name = agent.get("name") or bc_id
        lines = convert_transcript(
            transcript,
            composer_id=bc_id,
            workspace=str(workspace),
            git_remote=resolved_remote,
            cloud_agent_name=cloud_agent_name,
        )
        if not lines:
            continue

        output_file = bucket_dir / f"{bc_id}.jsonl"
        with output_file.open("w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")

        manifest_sessions.append(
            {
                "bcId": bc_id,
                "cloud_agent_name": cloud_agent_name,
                "jsonl": f"{bucket_name}/{bc_id}.jsonl",
                "source_transcript": str(transcript_path),
            }
        )
        converted += 1

    metadata = {
        "version": 1,
        "directories": {
            bucket_name: {
                "git_remote": resolved_remote,
                "cwd": str(workspace),
            }
        },
    }
    with (output_dir / "_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    manifest = {
        "version": 1,
        "workspace": str(workspace),
        "git_remote": resolved_remote,
        "bucket": bucket_name,
        "session_count": converted,
        "sessions": manifest_sessions,
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Cursor Cloud Agent transcript exports to Paxel JSONL staging files."
    )
    parser.add_argument(
        "--export-dir",
        default=DEFAULT_EXPORT_DIR,
        help=f"Directory containing index.json and bc-*/transcript.json (default: {DEFAULT_EXPORT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Staging output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Absolute path to the project workspace",
    )
    parser.add_argument(
        "--git-remote",
        default=None,
        help="Optional git remote override (otherwise read from workspace origin)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    export_dir = Path(args.export_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()

    if not export_dir.is_dir():
        print(f"Export directory not found: {export_dir}", file=sys.stderr)
        return 1
    if not workspace.is_dir():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 1

    try:
        manifest = convert_exports(export_dir, output_dir, workspace, args.git_remote)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Converted {manifest['session_count']} cloud agent session(s) "
        f"to {output_dir / manifest['bucket']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
