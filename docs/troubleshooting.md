# Troubleshooting

Common issues and how to resolve them.

## Export and conversion

### `Export directory not found`

The wrapper could not find `cloud-agent-transcripts-export`.

**Fix:**

1. Export transcripts first (see [Exporting transcripts](exporting-transcripts.md))
2. Place the directory at `<project>/cloud-agent-transcripts-export`, or
3. Set `EXPORT_DIR=/path/to/export` before running the wrapper

### `Missing index file: .../index.json`

The export directory exists but lacks `index.json`.

**Fix:** Ensure your export includes `index.json` with an `agents` array. If using MCP `batch-fetch-details`, the tool writes this automatically.

### `No agents listed in index.json`

`index.json` exists but the `agents` array is empty.

**Fix:** Re-run `batch-fetch-details` with valid `bc_ids`, or add agent entries manually.

### `Missing transcript for bc-...`

An agent is listed in `index.json` but has no `transcript.json`.

**Fix:**

- Call `batch-fetch-details` with `include_transcripts: true`
- Ensure the directory is named `bc-<id>/` or `<id>/`
- Remove agents without transcripts from `index.json`

### `Converted 0 cloud agent session(s)`

Conversion ran but no sessions were written.

**Causes:**

- All transcripts have empty `messages` arrays
- Transcript JSON is malformed

**Fix:** Open `transcript.json` and verify it contains `messages` with `user`, `assistant`, or `tool` roles.

### `Conversion failed: ... JSONDecodeError`

A transcript or index file is not valid JSON.

**Fix:** Validate JSON with `python3 -m json.tool <file>` and fix syntax errors.

## Paxel upload

### `Patch anchor not found for ...`

Paxel's `upload.sh` has changed and no longer matches the expected text.

**Fix:** This is a compatibility break. Open an issue on the [GitHub repo](https://github.com/Salestrics/Cursor-Cloud-to-Paxel-Converter) with the Paxel upload script version/date. As a workaround, run manual conversion only and inspect whether a newer converter release is available.

### Docker not running

Paxel requires Docker for session analysis.

**Fix:**

```bash
docker info   # should succeed
```

Start Docker Desktop or the Docker daemon, then retry.

### `YC_TOKEN is not set` warning

Informational only. Paxel can authenticate via browser.

**Fix (optional):** Set `YC_TOKEN` if you have a Paxel API token:

```bash
export YC_TOKEN="your-token"
```

### Sessions don't appear in Paxel

**Checklist:**

1. Did conversion report `Converted N cloud agent session(s)` with N > 0?
2. Is `PAXEL_CLOUD_AGENT_CURSOR_DIR` pointing at the staging directory? (The wrapper sets this automatically.)
3. Does the git remote in staging match your Paxel project? Run:

   ```bash
   head -1 ~/.paxel/cloud-agent-cursor-staging/_cursor_*/*.jsonl | python3 -m json.tool
   ```

   and verify `_cursor_meta.git_remote` matches your repo.

4. Try `--since all` to include older sessions:

   ```bash
   ./paxel-upload-with-cloud-agents.sh /path/to/project --since all
   ```

### Wrong project selected in Paxel

Paxel auto-detects projects by git remote. If you have multiple remotes or a fork:

**Fix:** Pass an explicit git remote to the converter:

```bash
python3 convert-cloud-agent-transcripts-to-paxel.py \
  --export-dir cloud-agent-transcripts-export \
  --workspace /path/to/project \
  --git-remote https://github.com/org/correct-repo
```

## MCP export

### `batch-fetch-details` returns no agents

**Causes:**

- `bc_ids` don't match accessible agents
- Agents are on a different repository than the current environment

**Fix:** Call `list-cloud-agents` first to get valid `bcId` values for your repo.

### Transcripts too large

Cloud Agent transcripts can be very large.

**Fix:**

- Export fewer agents per batch (max 50 per `batch-fetch-details` call)
- Filter with `created_after` or `did_make_code_changes: true` in `list-cloud-agents`

## General

### Re-running the upload

Each conversion **clears** the staging directory. Re-export and re-run the wrapper to pick up new Cloud Agent sessions.

### Getting help

1. Check [Getting started](getting-started.md) and [Reference](reference.md)
2. Run conversion manually to isolate the failure:

   ```bash
   python3 convert-cloud-agent-transcripts-to-paxel.py \
     --export-dir cloud-agent-transcripts-export \
     --workspace /path/to/project
   ```

3. Open an issue at [github.com/Salestrics/Cursor-Cloud-to-Paxel-Converter](https://github.com/Salestrics/Cursor-Cloud-to-Paxel-Converter/issues) with the error message and steps to reproduce
