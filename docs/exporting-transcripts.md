# Exporting transcripts

Cursor Cloud Agents store conversation history remotely. Paxel's official upload script only reads **local** transcripts (Claude `~/.claude`, Codex `~/.codex`, desktop Cursor `workspaceStorage`). This converter bridges that gap by accepting a standard export layout.

## Required export layout

```text
cloud-agent-transcripts-export/
  index.json
  bc-<agent-id>/
    transcript.json
  bc-<another-id>/
    transcript.json
```

### `index.json`

Lists the agents included in the export. The converter reads the `agents` array:

```json
{
  "agents": [
    {
      "bcId": "bc-abc123",
      "name": "Fix login bug",
      "status": "IDLE",
      "createdAt": "2026-07-14T01:00:00Z"
    }
  ]
}
```

Required fields per agent:

| Field | Required | Description |
|-------|----------|-------------|
| `bcId` | Yes | Cloud Agent ID (e.g. `bc-abc123`) |
| `name` | No | Display name (falls back to `bcId`) |

### `transcript.json`

Per-agent conversation export. The converter expects a `messages` array with roles `user`, `assistant`, and `tool`:

```json
{
  "messages": [
    {
      "role": "user",
      "text": "Fix the login bug",
      "started_at_ms": 1720915200000
    },
    {
      "role": "assistant",
      "text": "I'll investigate the auth module.",
      "thinking": "Let me start by reading the login handler...",
      "tool_calls": [
        {
          "tool_name": "Read",
          "tool_args": { "path": "src/auth.ts" },
          "tool_call_id": "call_abc"
        }
      ],
      "started_at_ms": 1720915201000
    },
    {
      "role": "tool",
      "tool_call_id": "call_abc",
      "tool_result": { "value": { "contents": "..." } },
      "completed_at_ms": 1720915202000
    }
  ]
}
```

Transcript directories may be named `bc-<id>` or `<id>` (with or without the `bc-` prefix) — the converter checks both.

## Method 1: Cursor Cloud MCP (recommended)

If you have access to the Cursor Cloud MCP server in Cursor, use these tools:

### 1. List agents

Call `list-cloud-agents` to find sessions for your repository. Useful filters:

- `did_make_code_changes: true` — only agents that changed code
- `created_after` — ISO-8601 UTC timestamp to limit scope
- `limit` / `offset` — pagination (max 200 per page)

Each result includes a `bcId` you need for the next step.

### 2. Batch-fetch transcripts

Call `batch-fetch-details` with:

```json
{
  "bc_ids": ["bc-abc123", "bc-def456"],
  "include_transcripts": true
}
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `include_transcripts` | `false` | **Required** — writes `transcript.json` per agent |
| `include_diff_metadata` | `false` | PR link, change counts (not used by converter) |
| `include_setup_logs` | `false` | Pod setup logs (not used by converter) |
| `include_environment` | `false` | Environment config (not used by converter) |

The tool writes files under `/tmp/cursor/cloud-agent-transcripts/<datetime-id>/`:

```text
/tmp/cursor/cloud-agent-transcripts/2026-07-14T01-00-00/
  index.json
  bc-abc123/
    transcript.json
```

### 3. Copy to your project

Copy the export directory to one of the locations the wrapper checks:

```bash
cp -r /tmp/cursor/cloud-agent-transcripts/2026-07-14T01-00-00 \
  /path/to/your/project/cloud-agent-transcripts-export
```

Or set `EXPORT_DIR` to point at the temp directory directly.

> **Note:** `batch-fetch-details` accepts up to 50 `bc_ids` per call. For larger batches, split into multiple calls and merge the `agents` arrays in `index.json`.

## Method 2: Ask a Cloud Agent to export

When running inside a Cursor Cloud Agent environment, you can ask the agent to:

1. Call `list-cloud-agents` to find relevant sessions
2. Call `batch-fetch-details` with `include_transcripts: true`
3. Copy the output to `cloud-agent-transcripts-export/` in the project

The wrapper script checks `<project>/cloud-agent-transcripts-export` automatically.

## Method 3: Manual export

If you have transcript JSON from another source, assemble the layout manually:

1. Create `cloud-agent-transcripts-export/index.json` with your agent list
2. Create `cloud-agent-transcripts-export/bc-<id>/transcript.json` for each agent
3. Ensure message roles and tool call fields match the format above

## Export directory resolution

The wrapper (`paxel-upload-with-cloud-agents.sh`) resolves the export directory in this order:

1. `$EXPORT_DIR` if set
2. `$PROJECT_DIR/cloud-agent-transcripts-export`
3. `$CONVERTER_DIR/cloud-agent-transcripts-export`

## Tips

- **Export only what you need.** Transcripts can be large; filter by date or `did_make_code_changes` before fetching.
- **Re-export before each upload.** The converter clears the staging directory on each run.
- **Match the workspace.** Pass the same project path you used when running the Cloud Agent so git remote matching works in Paxel.
