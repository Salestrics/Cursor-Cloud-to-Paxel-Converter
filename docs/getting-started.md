# Getting started

This guide walks you through exporting Cursor Cloud Agent transcripts and uploading them to Paxel.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.8+** | Used by the converter and patch scripts |
| **bash** | Wrapper script and Paxel upload |
| **curl** | Downloads Paxel's `upload.sh` |
| **Docker** | Required by Paxel for session analysis |
| **Git repo** | Your project should be a git repository (for remote matching) |
| **Cursor Cloud MCP** | For automated export via `automate-bridge.sh` |
| **Exported transcripts** | Or prepare manually — see [Exporting transcripts](exporting-transcripts.md) |

Optional:

- **`YC_TOKEN`** — Paxel API token (browser auth works without it)
- **`jq`** — Helpful for Paxel remote detection from staging JSONL (not required when using cloud staging only)

## Install

```bash
git clone https://github.com/Salestrics/Cursor-Cloud-to-Paxel-Converter.git
cd Cursor-Cloud-to-Paxel-Converter
chmod +x automate-bridge.sh paxel-upload-with-cloud-agents.sh
```

No `pip install` step — the converter uses only the Python standard library.

## Step 1: Export and upload (automated)

From a **Cursor Agent** with Cloud MCP access:

```bash
# 1. Agent calls list-cloud-agents + batch-fetch-details (include_transcripts: true)
# 2. Run one command:
export YC_TOKEN="your-token"   # optional
./automate-bridge.sh /path/to/your/project --since 2m --zip
```

This merges the latest MCP export, converts to Paxel JSONL, patches `upload.sh`, and uploads.

## Step 1 (manual): Export Cloud Agent transcripts

If you are not using `automate-bridge.sh`, prepare a directory with this layout:

```text
cloud-agent-transcripts-export/
  index.json
  bc-<agent-id>/
    transcript.json
```

The easiest path is the Cursor Cloud MCP `batch-fetch-details` tool with `include_transcripts: true`. See [Exporting transcripts](exporting-transcripts.md) for full instructions.

Place the export at one of these locations (checked in order):

1. `$EXPORT_DIR` environment variable
2. `<your-project>/cloud-agent-transcripts-export`
3. `<converter-repo>/cloud-agent-transcripts-export`

## Step 2: Upload to Paxel (manual export)

If you exported transcripts manually, run:

```bash
./paxel-upload-with-cloud-agents.sh /path/to/your/project --since 2m
```

The `--since` flag is passed through to Paxel's upload script (e.g. `2m`, `7d`, `all`).

### What the wrapper does

1. Locates your transcript export directory
2. Runs `convert-cloud-agent-transcripts-to-paxel.py` to build staging JSONL
3. Downloads Paxel's latest `upload.sh` from `https://paxel.ycombinator.com/upload.sh`
4. Patches it with `patch-paxel-for-cloud-agents.py`
5. Sets `PAXEL_CLOUD_AGENT_CURSOR_DIR` and runs the patched upload from your project

### Environment variables

```bash
# Optional: Paxel API token (skip browser sign-in)
export YC_TOKEN="your-token"

# Optional: override export directory
export EXPORT_DIR=/path/to/cloud-agent-transcripts-export

# Optional: override staging output (default: ~/.paxel/cloud-agent-cursor-staging)
export PAXEL_CLOUD_AGENT_CURSOR_DIR=~/.paxel/cloud-agent-cursor-staging
```

## Step 3: Verify in Paxel

After upload completes, open [Paxel](https://paxel.ycombinator.com) and confirm your Cloud Agent sessions appear alongside any local Cursor/Claude/Codex history for the same repository.

Sessions are tagged with `cloud_agent_name` in the JSONL metadata so you can distinguish Cloud Agent runs from desktop Cursor sessions.

## Manual conversion (without upload)

If you only want to convert transcripts without running Paxel:

```bash
python3 convert-cloud-agent-transcripts-to-paxel.py \
  --export-dir cloud-agent-transcripts-export \
  --workspace /path/to/your/project \
  --output-dir ~/.paxel/cloud-agent-cursor-staging
```

Then run Paxel yourself with `PAXEL_CLOUD_AGENT_CURSOR_DIR` set to the output directory. See [Reference](reference.md) for all CLI options.

## Next steps

- [Exporting transcripts](exporting-transcripts.md) — MCP workflow and manual export
- [Architecture](architecture.md) — how conversion and patching work
- [Troubleshooting](troubleshooting.md) — if something goes wrong
