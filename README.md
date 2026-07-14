# Cursor Cloud to Paxel Converter

Unofficial bridge that uploads **Cursor Cloud Agent** sessions to [Paxel by YC](https://paxel.ycombinator.com).

Paxel's official `upload.sh` only reads **local** transcripts (Claude `~/.claude`, Codex `~/.codex`, desktop Cursor `workspaceStorage`). Cursor Cloud Agents store sessions remotely. This tool:

1. Exports Cloud Agent transcripts (via Cursor MCP or manual export)
2. Converts them to Paxel's Cursor JSONL format
3. Patches Paxel's `upload.sh` to import the staging directory
4. Runs the patched upload from your project

## Quick start

### 1. Export Cloud Agent transcripts

Use the Cursor Cloud MCP `batch-fetch-details` tool (or any export that produces this layout):

```text
cloud-agent-transcripts-export/
  index.json
  bc-<agent-id>/
    transcript.json
```

Place the export at one of:

- `$EXPORT_DIR` (env var)
- `<project>/cloud-agent-transcripts-export`
- `<converter>/cloud-agent-transcripts-export`

### 2. Upload to Paxel

```bash
git clone https://github.com/Salestrics/Cursor-Cloud-to-Paxel-Converter.git
cd Cursor-Cloud-to-Paxel-Converter
chmod +x paxel-upload-with-cloud-agents.sh

# From anywhere, pointing at your project:
./paxel-upload-with-cloud-agents.sh /path/to/your/project --since 2m
```

Set `YC_TOKEN` if you already have a Paxel API token. Docker must be installed and running.

## Manual conversion

```bash
python3 convert-cloud-agent-transcripts-to-paxel.py \
  --export-dir cloud-agent-transcripts-export \
  --workspace /path/to/your/project \
  --output-dir ~/.paxel/cloud-agent-cursor-staging
```

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--export-dir` | `cloud-agent-transcripts-export` | Directory with `index.json` and `bc-*/transcript.json` |
| `--output-dir` | `~/.paxel/cloud-agent-cursor-staging` | Paxel staging directory |
| `--workspace` | *(required)* | Project workspace path |
| `--git-remote` | origin URL | Optional git remote override |

### Output layout

```text
~/.paxel/cloud-agent-cursor-staging/
  _metadata.json
  manifest.json
  _cursor_<projectName>_<hash6>/
    bc-<agent-id>.jsonl
```

Each JSONL file uses Paxel's Cursor format. The first line includes `_cursor_meta` with `composerId`, `workspace`, `git_remote`, `agent_type="cursor"`, and `cloud_agent_name`.

## What gets patched in Paxel upload.sh

`patch-paxel-for-cloud-agents.py` applies seven in-place edits to the downloaded Paxel script:

1. **`collect_cursor_sessions()`** — copies staging JSONL when `PAXEL_CLOUD_AGENT_CURSOR_DIR` is set
2. **`session_count`** — includes cloud import count from staging
3. **Auto-detect** — skips the "none match" prompt when cloud staging has sessions
4. **`maybe_prescan_cursor_remotes`** — works without a local Cursor SQLite DB
5. **`_paxel_should_run_cursor_extraction()`** — helper injected before `run_docker_analysis()`
6. **Docker cursor mount gate** — uses the helper (cloud imports do not require `jq`/`sqlite3`)
7. **Missing-tools hint** — suppressed when cloud staging is in use

## Tool name mapping

Cloud Agent tool names are normalized to Paxel's Cursor names:

| Cloud Agent | Paxel |
|-------------|-------|
| `run_terminal_cmd`, `Shell` | `Bash` |
| `read`, `read_file`, `Read` | `Read` |
| `write`, `StrReplace`, `Edit` | `Edit` |
| `grep`, `Grep` | `Grep` |
| `glob_file_search`, `Glob` | `Glob` |
| `Task` | `Task` |

## Files

| File | Purpose |
|------|---------|
| `convert-cloud-agent-transcripts-to-paxel.py` | Cloud transcript → Paxel JSONL converter |
| `patch-paxel-for-cloud-agents.py` | Patches downloaded Paxel `upload.sh` |
| `paxel-upload-with-cloud-agents.sh` | End-to-end wrapper script |

## Requirements

- Python 3.8+
- `curl`, `bash`
- Docker (for Paxel analysis)
- Exported Cloud Agent transcripts (`index.json` + per-agent `transcript.json`)

## License

MIT © 2026 Salestrics
