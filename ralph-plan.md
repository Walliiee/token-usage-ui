# Token Usage UI — Ralph Loop Plan

**Goal:** Build a local UI for token usage overview.

**Methodology:** Ralph Loops (Build -> Test -> Confirm -> Next).
- Minimax (Fast): Scaffolding, HTML/CSS/JS frontend work.
- GLM-Pro (Deep): Python backend logic, data fetching, math, API endpoints.

## Loop Status
- [x] **Loop 1 (Minimax):** Scaffold project, `index.html`, basic Python HTTP server.
- [x] **Loop 2 (GLM-Pro):** Implement a Python script to fetch token usage data (e.g. from `openclaw status --usage --json` or parsing `.openclaw` logs) and serve it as a JSON endpoint in `server.py`. Test that the endpoint returns valid JSON.
- [x] **Loop 3 (Minimax):** Update `index.html` to fetch the JSON endpoint and display the raw data on the page. Test that data appears. ✅ (Real data from 323 sessions across 10 models confirmed via curl — input/output tokens + session counts all render correctly.)
- [x] **Loop 4 (GLM-Pro):** Add historical data processing (reading from OpenClaw sqlite or log history) to provide a timeline of token usage.
- [x] **Loop 5 (Minimax):** Add a Chart.js (or similar) chart to the frontend to visualize the timeline data.
- [x] **Loop 6 (GLM-Pro):** Refine data into cost estimates (applying pricing rules for models).
- [x] **Loop 7 (Minimax):** Add a dashboard layout showing cost metrics and top model usage.
- [x] **Loop 8 (GLM-Pro):** Add a live-reload or background polling mechanism so data is fresh.
- [x] **Loop 9 (Minimax):** Polish UI/UX (dark mode refinements, animations). ✅
- [x] **Loop 10 (System):** Final review and cleanup. ✅