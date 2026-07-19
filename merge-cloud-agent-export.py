#!/usr/bin/env python3
"""Merge Cursor Cloud MCP batch-fetch exports into a persistent project export."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

DEFAULT_EXPORT_DIR = "cloud-agent-transcripts-export"
MCP_EXPORT_ROOT = Path("/tmp/cursor/cloud-agent-transcripts")


def normalize_bc_id(bc_id: str) -> str:
    bc_id = bc_id.strip()
    if not bc_id:
        return bc_id
    return bc_id if bc_id.startswith("bc-") else f"bc-{bc_id}"


def agent_dir_names(bc_id: str) -> list[str]:
    bare = bc_id.removeprefix("bc-")
    return [bc_id, f"bc-{bare}", bare]


def load_agents(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.is_file():
        return []
    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload.get("agents") or [])


def write_index(dest_dir: Path, agents: list[dict[str, Any]]) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    index_path = dest_dir / "index.json"
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump({"agents": agents}, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def agent_index(agents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for agent in agents:
        bc_id = agent.get("bcId")
        if bc_id:
            indexed[normalize_bc_id(str(bc_id))] = agent
    return indexed


def find_agent_dir(export_dir: Path, bc_id: str) -> Path | None:
    for name in agent_dir_names(bc_id):
        candidate = export_dir / name
        if candidate.is_dir():
            return candidate
    return None


def copy_agent_export(source_dir: Path, dest_dir: Path, bc_id: str) -> Path:
    source_agent_dir = find_agent_dir(source_dir, bc_id)
    if source_agent_dir is None:
        raise FileNotFoundError(f"Missing agent directory for {bc_id} in {source_dir}")

    transcript = source_agent_dir / "transcript.json"
    if not transcript.is_file():
        raise FileNotFoundError(f"Missing transcript for {bc_id}: {transcript}")

    dest_agent_dir = dest_dir / normalize_bc_id(bc_id)
    if dest_agent_dir.exists():
        shutil.rmtree(dest_agent_dir)
    shutil.copytree(source_agent_dir, dest_agent_dir)
    return dest_agent_dir


def merge_exports(
    source_dir: Path,
    dest_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    dest_dir = dest_dir.resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source export not found: {source_dir}")

    source_agents = load_agents(source_dir / "index.json")
    if not source_agents:
        raise ValueError(f"No agents found in {source_dir / 'index.json'}")

    dest_agents = load_agents(dest_dir / "index.json")
    dest_by_id = agent_index(dest_agents)

    added: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for agent in source_agents:
        bc_id = agent.get("bcId")
        if not bc_id:
            continue
        normalized = normalize_bc_id(str(bc_id))

        if normalized in dest_by_id and not force:
            skipped.append(normalized)
            continue

        copy_agent_export(source_dir, dest_dir, normalized)
        dest_by_id[normalized] = agent
        if normalized in skipped:
            skipped.remove(normalized)
        if normalized in dest_agents and force:
            updated.append(normalized)
        else:
            added.append(normalized)

    merged_agents = list(dest_by_id.values())
    merged_agents.sort(key=lambda item: str(item.get("createdAt") or item.get("bcId") or ""))
    write_index(dest_dir, merged_agents)

    return {
        "source": str(source_dir),
        "dest": str(dest_dir),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "total": len(merged_agents),
    }


def find_latest_mcp_export(root: Path = MCP_EXPORT_ROOT) -> Path | None:
    if not root.is_dir():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def missing_bc_ids(dest_dir: Path, candidate_ids: list[str]) -> list[str]:
    dest_by_id = agent_index(load_agents(dest_dir / "index.json"))
    return [normalize_bc_id(bc_id) for bc_id in candidate_ids if normalize_bc_id(bc_id) not in dest_by_id]


def zip_export(export_dir: Path, zip_path: Path | None = None) -> Path:
    export_dir = export_dir.resolve()
    if zip_path is None:
        zip_path = export_dir.with_suffix(".zip")
    else:
        zip_path = zip_path.resolve()

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(export_dir.parent).as_posix())
    return zip_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge a Cursor Cloud MCP batch-fetch export into a persistent project export."
    )
    parser.add_argument(
        "--source",
        help="MCP batch-fetch export directory (default: latest under /tmp/cursor/cloud-agent-transcripts)",
    )
    parser.add_argument(
        "--dest",
        default=DEFAULT_EXPORT_DIR,
        help=f"Destination export directory (default: {DEFAULT_EXPORT_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite agents that already exist in the destination export",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Refresh <dest>.zip after merging",
    )
    parser.add_argument(
        "--list-missing",
        metavar="BC_ID",
        nargs="+",
        help="Print bc_ids from the arguments that are not yet in --dest, then exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dest_dir = Path(args.dest).expanduser().resolve()

    if args.list_missing is not None:
        missing = missing_bc_ids(dest_dir, args.list_missing)
        for bc_id in missing:
            print(bc_id)
        return 0

    source_dir = Path(args.source).expanduser().resolve() if args.source else find_latest_mcp_export()
    if source_dir is None:
        print(
            "No MCP export directory found. Run batch-fetch-details first or pass --source.",
            file=sys.stderr,
        )
        return 1

    try:
        result = merge_exports(source_dir, dest_dir, force=args.force)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Merge failed: {exc}", file=sys.stderr)
        return 1

    if args.zip:
        zip_path = zip_export(dest_dir)
        result["zip"] = str(zip_path)

    print(
        f"Merged export at {result['dest']}: "
        f"{len(result['added'])} added, {len(result['updated'])} updated, "
        f"{len(result['skipped'])} skipped ({result['total']} total)"
    )
    if result["added"]:
        print("Added:", ", ".join(result["added"]))
    if result["updated"]:
        print("Updated:", ", ".join(result["updated"]))
    if args.zip:
        print(f"Zip: {result['zip']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
