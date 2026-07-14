# Reference

CLI options, environment variables, output formats, and tool name mapping.

## Scripts

| File | Purpose |
|------|---------|
| `convert-cloud-agent-transcripts-to-paxel.py` | Cloud transcript → Paxel JSONL converter |
| `patch-paxel-for-cloud-agents.py` | Patches downloaded Paxel `upload.sh` |
| `paxel-upload-with-cloud-agents.sh` | End-to-end wrapper |

## `convert-cloud-agent-transcripts-to-paxel.py`

```bash
python3 convert-cloud-agent-transcripts-to-paxel.py \
  --export-dir <path> \
  --workspace <path> \
  [--output-dir <path>] \
  [--git-remote <url>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--export-dir` | `cloud-agent-transcripts-export` | Directory with `index.json` and `bc-*/transcript.json` |
| `--output-dir` | `~/.paxel/cloud-agent-cursor-staging` | Paxel staging directory (cleared on each run) |
| `--workspace` | *(required)* | Absolute path to the project workspace |
| `--git-remote` | `origin` URL | Optional git remote override |

**Exit codes:** `0` success, `1` error (missing dirs, bad JSON, no agents).

## `patch-paxel-for-cloud-agents.py`

```bash
python3 patch-paxel-for-cloud-agents.py /path/to/upload.sh
```

Applies eight in-place patches (seven functional areas; `session_count` is patched in two code paths). Prints each applied patch or `skip (already applied): ...` for idempotent re-runs.

**Exit codes:** `0` success, `1` error (file not found, anchor not found).

## `paxel-upload-with-cloud-agents.sh`

```bash
./paxel-upload-with-cloud-agents.sh /path/to/project [--since <duration>]
```

| Argument | Description |
|----------|-------------|
| `/path/to/project` | Project workspace (required) |
| `--since` | Passed to Paxel upload (e.g. `2m`, `7d`, `all`) |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPORT_DIR` | *(see resolution order)* | Override transcript export directory |
| `PAXEL_CLOUD_AGENT_CURSOR_DIR` | `~/.paxel/cloud-agent-cursor-staging` | Staging output; read by patched Paxel upload |
| `YC_TOKEN` | *(unset)* | Paxel API token (optional; browser auth works) |

### Export directory resolution

1. `$EXPORT_DIR` if set
2. `$PROJECT_DIR/cloud-agent-transcripts-export`
3. `$CONVERTER_DIR/cloud-agent-transcripts-export`

## Output layout

```text
~/.paxel/cloud-agent-cursor-staging/
  _metadata.json          # Paxel directory metadata
  manifest.json           # Converter manifest (session list)
  _cursor_<project>_<hash>/
    bc-<agent-id>.jsonl    # One file per Cloud Agent session
```

### `manifest.json`

```json
{
  "version": 1,
  "workspace": "/path/to/project",
  "git_remote": "https://github.com/org/repo",
  "bucket": "_cursor_myapp_a1b2c3",
  "session_count": 2,
  "sessions": [
    {
      "bcId": "bc-abc123",
      "cloud_agent_name": "Fix login bug",
      "jsonl": "_cursor_myapp_a1b2c3/bc-abc123.jsonl",
      "source_transcript": "/path/to/export/bc-abc123/transcript.json"
    }
  ]
}
```

### `_metadata.json`

```json
{
  "version": 1,
  "directories": {
    "_cursor_myapp_a1b2c3": {
      "git_remote": "https://github.com/org/repo",
      "cwd": "/path/to/project"
    }
  }
}
```

## Tool name mapping

Cloud Agent tool names are normalized to Paxel's Cursor names:

| Cloud Agent | Paxel |
|-------------|-------|
| `run_terminal_cmd`, `run_terminal_command_v2`, `Shell` | `Bash` |
| `read`, `read_file`, `read_file_v2`, `Read` | `Read` |
| `write`, `StrReplace`, `Edit`, `edit_file`, `edit_file_v2`, `search_replace` | `Edit` |
| `grep`, `Grep`, `ripgrep_raw_search` | `Grep` |
| `glob_file_search`, `glob_file_search_v2`, `Glob` | `Glob` |
| `Task`, `task_v2` | `Task` |

Unmapped names pass through unchanged.

### Tool input remapping

| Paxel tool | Cloud field | Mapped to |
|------------|-------------|-----------|
| `Read` | `target_file`, `path` | `file_path` |
| `Edit` | `relativeWorkspacePath`, `target_file` | `file_path` |
| `Bash` | `command` | `cmd` |

## Requirements

- Python 3.8+
- `curl`, `bash`
- Docker (for Paxel analysis)
- Exported Cloud Agent transcripts
