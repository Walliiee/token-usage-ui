#!/usr/bin/env python3
"""HTTP server for the Token Usage UI.

Serves the dashboard (index.html) plus two JSON endpoints:

  GET /api/usage     aggregated per-model token usage and estimated cost
  GET /api/timeline  daily token usage time-series (last entries)

Session data is read from ``$OPENCLAW_DIR/agents/main/sessions/sessions.json``.
If no real data is found, representative mock data is returned so the UI can
still be demoed.
"""
import http.server
import json
import os
import socketserver
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PORT = int(os.environ.get("PORT", "8765"))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_DIR = Path(os.environ.get("OPENCLAW_DIR", Path.home() / ".openclaw"))

# Pricing: cost per 1M tokens (input, output).
# Listed longest-prefix-first so the first match wins correctly.
MODEL_PRICING = [
    # Anthropic — specific model IDs first, then family prefixes
    ("claude-sonnet-4-6",        (3.0,  15.0)),
    ("claude-sonnet-4-20250514", (3.0,  15.0)),
    ("claude-3-5-sonnet",        (3.0,  15.0)),
    ("claude-haiku-4-5",         (0.8,   4.0)),
    ("claude-3-5-haiku",         (0.8,   4.0)),
    ("claude-haiku-3-5",         (0.8,   4.0)),
    ("claude-3-haiku",           (0.25,  1.25)),
    ("claude-opus-4-7",          (15.0, 75.0)),
    ("claude-opus-4",            (15.0, 75.0)),
    ("claude-3-opus",            (15.0, 75.0)),
    # Local / cloud models — free
    ("glm-5.1:cloud",            (0.0,   0.0)),
    ("glm-5:cloud",              (0.0,   0.0)),
    ("kimi-k2.5:cloud",          (0.0,   0.0)),
    ("minimax-m2.7:cloud",       (0.0,   0.0)),
    ("qwen3.6:cloud",            (0.0,   0.0)),
]


def now_iso():
    """Return the current UTC time as an ISO-8601 string with a 'Z' suffix."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def get_pricing(model):
    """Return (input_per_1M, output_per_1M) for a model, with longest-prefix matching."""
    for prefix, price in MODEL_PRICING:
        if model == prefix or model.startswith(prefix):
            return price
    return (0.0, 0.0)


def calc_cost(inp, out, model):
    """Calculate estimated cost in USD for given tokens and model."""
    p_in, p_out = get_pricing(model)
    return round((inp / 1_000_000) * p_in + (out / 1_000_000) * p_out, 4)


def load_sessions():
    """Load session records from sessions.json; returns a list of dicts."""
    sessions_file = OPENCLAW_DIR / "agents" / "main" / "sessions" / "sessions.json"
    if not sessions_file.exists():
        return []
    try:
        data = json.loads(sessions_file.read_text())
        if isinstance(data, list):
            return [s for s in data if isinstance(s, dict)]
        if isinstance(data, dict):
            return [s for s in data.values() if isinstance(s, dict)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def get_usage_data():
    """Aggregate per-model token usage and cost across all sessions."""
    sessions = load_sessions()
    models = {}
    total_sessions = len(sessions)

    for s in sessions:
        model = s.get("model", "unknown")
        inp = s.get("inputTokens", 0) or 0
        out = s.get("outputTokens", 0) or 0
        entry = models.setdefault(
            model, {"inputTokens": 0, "outputTokens": 0, "sessions": 0}
        )
        entry["inputTokens"] += inp
        entry["outputTokens"] += out
        entry["sessions"] += 1

    # If no real data, return mock so the frontend can be demoed.
    if not models:
        models = {
            "glm-5.1:cloud": {"inputTokens": 8200, "outputTokens": 3850, "sessions": 5},
            "kimi-k2.5:cloud": {"inputTokens": 15000, "outputTokens": 6200, "sessions": 3},
            "minimax-m2.7:cloud": {"inputTokens": 4300, "outputTokens": 1900, "sessions": 2},
        }
        total_sessions = 10

    for model, d in models.items():
        d["cost"] = calc_cost(d["inputTokens"], d["outputTokens"], model)
    total_cost = sum(d["cost"] for d in models.values())

    return {
        "totalSessions": total_sessions,
        "models": models,
        "totalCost": round(total_cost, 4),
        "fetchedAt": now_iso(),
    }


def get_timeline_data():
    """Return daily token usage time-series from sessions.json."""
    def empty_models():
        return defaultdict(lambda: {"inputTokens": 0, "outputTokens": 0, "sessions": 0})

    def empty_day():
        return {"inputTokens": 0, "outputTokens": 0, "sessions": 0, "models": empty_models()}

    by_date = defaultdict(empty_day)

    for s in load_sessions():
        ts = s.get("startedAt")
        if not ts:
            continue
        date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        model = s.get("model", "unknown")
        inp = s.get("inputTokens") or 0
        out = s.get("outputTokens") or 0
        day = by_date[date_str]
        day["inputTokens"] += inp
        day["outputTokens"] += out
        day["sessions"] += 1
        day["models"][model]["inputTokens"] += inp
        day["models"][model]["outputTokens"] += out
        day["models"][model]["sessions"] += 1

    # Build a sorted array and compute per-day, per-model cost.
    timeline = []
    for date_str in sorted(by_date.keys()):
        entry = {"date": date_str, **by_date[date_str]}
        entry["models"] = dict(entry["models"])
        day_cost = 0.0
        for model, md in entry["models"].items():
            md["cost"] = calc_cost(md["inputTokens"], md["outputTokens"], model)
            day_cost += md["cost"]
        entry["cost"] = round(day_cost, 4)
        timeline.append(entry)

    # Fallback mock data for the last 7 days.
    if not timeline:
        today = datetime.now(timezone.utc).date()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            timeline.append({
                "date": d.strftime("%Y-%m-%d"),
                "inputTokens": 50000 * (i + 1),
                "outputTokens": 5000 * (i + 1),
                "sessions": i + 2,
                "models": {},
            })

    return {"timeline": timeline, "fetchedAt": now_iso()}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _send_json(self, payload):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/timeline":
            self._send_json(get_timeline_data())
        elif self.path == "/api/usage":
            self._send_json(get_usage_data())
        elif self.path in ("/", "/index.html"):
            body = (Path(DIRECTORY) / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src cdn.jsdelivr.net; "
                "style-src fonts.googleapis.com 'unsafe-inline'; "
                "font-src fonts.gstatic.com",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving Token Usage UI at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")


if __name__ == "__main__":
    main()
