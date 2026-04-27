#!/usr/bin/env python3
"""HTTP server for Token Usage UI with /api/usage endpoint."""
import http.server
import json
import os
import socketserver
from pathlib import Path
from datetime import datetime

PORT = 8765
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
    """Fetch real session data from OpenClaw sessions."""
    sessions = load_sessions()
    models = {}
    total_sessions = len(sessions)

    for s in sessions:
        model = s.get("model", "unknown")
        inp = s.get("inputTokens", 0) or 0
        out = s.get("outputTokens", 0) or 0
        if model not in models:
            models[model] = {"inputTokens": 0, "outputTokens": 0, "sessions": 0}
        models[model]["inputTokens"] += inp
        models[model]["outputTokens"] += out
        models[model]["sessions"] += 1

    # If no real data, return mock so frontend can wire up
    if not models:
        models = {
            "glm-5.1:cloud": {"inputTokens": 8200, "outputTokens": 3850, "sessions": 5},
            "kimi-k2.5:cloud": {"inputTokens": 15000, "outputTokens": 6200, "sessions": 3},
            "minimax-m2.7:cloud": {"inputTokens": 4300, "outputTokens": 1900, "sessions": 2},
        }
        total_sessions = 10

    # Add cost per model
    for model, d in models.items():
        d["cost"] = calc_cost(d["inputTokens"], d["outputTokens"], model)
    total_cost = sum(d["cost"] for d in models.values())
    return {"totalSessions": total_sessions, "models": models, "totalCost": round(total_cost, 4), "fetchedAt": datetime.utcnow().isoformat() + "Z"}

def get_timeline_data():
    """Return daily token usage time-series from sessions.json."""
    from collections import defaultdict
    import datetime as _dt
    by_date = defaultdict(lambda: {"inputTokens": 0, "outputTokens": 0, "sessions": 0, "models": defaultdict(lambda: {"inputTokens": 0, "outputTokens": 0, "sessions": 0})})

    for s in load_sessions():
        ts = s.get("startedAt")
        if not ts:
            continue
        date_str = _dt.datetime.fromtimestamp(ts / 1000, tz=_dt.timezone.utc).strftime("%Y-%m-%d")
        model = s.get("model", "unknown")
        inp = s.get("inputTokens") or 0
        out = s.get("outputTokens") or 0
        by_date[date_str]["inputTokens"] += inp
        by_date[date_str]["outputTokens"] += out
        by_date[date_str]["sessions"] += 1
        by_date[date_str]["models"][model]["inputTokens"] += inp
        by_date[date_str]["models"][model]["outputTokens"] += out
        by_date[date_str]["models"][model]["sessions"] += 1

    # Build sorted array
    timeline = []
    for date_str in sorted(by_date.keys()):
        entry = {"date": date_str, **by_date[date_str]}
        entry["models"] = dict(entry["models"])
        timeline.append(entry)

    # Add cost per day per model
    for entry in timeline:
        day_cost = 0.0
        for model, md in entry["models"].items():
            md["cost"] = calc_cost(md["inputTokens"], md["outputTokens"], model)
            day_cost += md["cost"]
        entry["cost"] = round(day_cost, 4)

    # Fallback mock data
    if not timeline:
        from datetime import timedelta
        today = datetime.utcnow().date()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            timeline.append({"date": d.strftime("%Y-%m-%d"), "inputTokens": 50000 * (i + 1), "outputTokens": 5000 * (i + 1), "sessions": i + 2, "models": {}})

    return {"timeline": timeline, "fetchedAt": datetime.utcnow().isoformat() + "Z"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/api/timeline":
            data = get_timeline_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        elif self.path == "/api/usage":
            data = get_usage_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy",
                "default-src 'self'; "
                "script-src cdn.jsdelivr.net; "
                "style-src fonts.googleapis.com 'unsafe-inline'; "
                "font-src fonts.gstatic.com"
            )
            index = Path(DIRECTORY) / "index.html"
            body = index.read_bytes()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        httpd.serve_forever()
