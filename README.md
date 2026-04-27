# Token Usage UI

A local dashboard for monitoring OpenClaw token usage, costs, and model breakdown.

## Quick Start

```bash
cd ~/.openclaw/workspace/projects/token-usage-ui
python server.py
```

Then open **http://localhost:8765** in your browser.

## What It Shows

- **Total API cost** (based on model pricing)
- **Per-model breakdown** — input/output tokens, cost, session count
- **7-day timeline chart** — daily token volume
- **Auto-refresh** every 8 seconds

## Data Source

Reads session data from `~/.openclaw/agents/main/sessions/sessions.json`. If no real data is found, mock data is used as a fallback.

Override the base directory with an environment variable if your install is non-default:

```bash
OPENCLAW_DIR=/custom/path python server.py
```

## Tech

- Python stdlib HTTP server (no dependencies)
- Chart.js (CDN) for the timeline
- Inter font (Google Fonts)
- Dark theme, responsive layout