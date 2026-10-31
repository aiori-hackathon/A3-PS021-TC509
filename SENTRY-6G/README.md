# SENTRY-6G — AIORI-3 / PS-021

**Experimental mock-adapter system** for dialog correlation, durable recovery, and executor-side idempotency. This package is a runnable prototype, not a production 6G deployment.

## Quick start (Windows PowerShell / Linux / macOS)

Requires Python 3.10+ (tested on Python 3.10.11).

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On Linux/macOS activate with `source .venv/bin/activate`.

Start **three separate terminals** from the project directory:

```powershell
# Terminal 1 — executor :8002
.\.venv\Scripts\python.exe service.py executor
# Terminal 2 — coordinator and dashboard :8001
.\.venv\Scripts\python.exe service.py coordinator
# Terminal 3 — requester :8000
.\.venv\Scripts\python.exe service.py requester
```

Linux/macOS: use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Open **http://127.0.0.1:8001** for the live dashboard. API docs at `http://127.0.0.1:8001/docs` and `http://127.0.0.1:8002/docs`.

Run the 11 automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Five reproducible scenarios

1. **Lost ACK after commit**: select `lost_ack`, run, then Recover. Expect `UNCERTAIN -> COMPLETED`, one effect.
2. **Duplicate request**: select `duplicate` using a new requester ID. Expect `duplicate_retry: true`, one effect.
3. **Partition before dispatch**: select `partition`, run, then Recover. Expect `UNKNOWN`, then `VERIFIED_NOT_EXECUTED` (no effect). The system deliberately does not automatically dispatch the operation after the partition.
4. **Coordinator restart**: select `restart`, run, stop and restart `python service.py coordinator`, then recover the dialog via `POST /recover/{dialog_id}` or dashboard (the dashboard's in-memory last-dialog selection resets on refresh). Expect persisted ID and one effect.
5. **Delay / reconnection**: select `delay` with RTT 350ms, run; alternatively stop executor, submit, restart executor, then recover. Expect UNKNOWN while unavailable; recovery may report NOT_EXECUTED.

**Important:** A `VERIFIED_NOT_EXECUTED` classification means absent from the *simulated executor ledger* at query time, not a general proof that arbitrary external operations did not occur. The executor stores the simulated effect and idempotency record in the same SQLite transaction. Real network commands require stronger transactional/reconciliation contracts.

## API examples

```bash
curl -X POST http://127.0.0.1:8000/delegate -H "Content-Type: application/json" -d '{"a_id":"A-42","command":"QoS=high","fault":"lost_ack"}'
curl http://127.0.0.1:8001/dialogs
curl http://127.0.0.1:8001/events
curl http://127.0.0.1:8001/network-policy?rtt_ms=250\&loss_pct=15
```

## Components

- `service.py requester` — independent mock Adapter A HTTP service, port 8000
- `service.py coordinator` — dialog FSM, SQLite journal, evidence gate, API, dashboard, port 8001
- `service.py executor` — mock Adapter B, authoritative effect ledger and deduplication, port 8002
- `core.py` — persistent SQLite model, transactionally atomic simulated effects
- `web/index.html` — no-build, offline-capable dashboard
- `tests/` — automated unit/concurrency tests

## Scope and limits

This is **not MCP/A2A interoperability**, **not a final IETF protocol**, and **not exactly-once delivery**. It is an experimental schema and mock adapter prototype. Network policy is a heuristic API, not an empirically validated adaptive scheduler. No B2 baseline comparison is included yet; do not claim performance superiority. The dashboard uses plain JavaScript rather than React to avoid a Node build dependency. There is no Docker configuration in this release. Do not connect this code to production routers or expose its unauthenticated APIs publicly.

## Evidence from local testing (2026-10-31)

The team reported 11/11 passing pytest checks and a five-scenario judge-demo PASS. The judge-demo reported executor ledger delta 4 (expected 4). These are **local mock-system observations**, not an independently validated 6G-network benchmark. The generated reports should be committed after reviewing for sensitive information. `reports/` is ignored by default; selectively force-add sanitized reports with `git add -f reports/<filename>`.

## GitHub submission

Create a private repository named for your team. Follow the official PS-021 PDF instructions regarding the `aiori-hackathon` collaborator and ownership transfer; verify the recipient and implications before transferring ownership. Include the proposal PDF, README, code, test evidence and mentor demonstration pseudocode. Do not commit `data/*.db` or credentials.

## Fast judge demo and evidence export

With executor (8002) and coordinator (8001) running in separate terminals (requester on 8000 for the full three-service demo):

```powershell
.\.venv\Scripts\python.exe judge_demo.py
```

This executes five distinct simulated fault cases against the running local services, checks executor evidence, and writes timestamped JSON and Markdown reports into `reports/`. The test checks the **change in executor effect count** across the run; it does not assert universal exactly-once semantics. A real coordinator restart is a **separate manual demonstration**, not part of this script. Run the automated tests with `python -m pytest -v`.

### 90-second judge presentation

1. Open the local dashboard at `http://127.0.0.1:8001`; explain three roles and separate SQLite journals.
2. Run `judge_demo.py` and show five scenario verdicts and the executor effect-count delta.
3. Open the generated Markdown report, explain UNKNOWN vs VERIFIED_DONE vs VERIFIED_NOT_EXECUTED.
4. Show duplicate retry and the executor ledger; explain the safety limit on uncertain outcomes.
5. For actual restart persistence, stop and restart only the coordinator service, then show the same dialog IDs and records.

**Submission:** Push source and tests to a private GitHub repository, add the official proposal and a demo recording or an accessible live demonstration link, and follow the event's collaborator/ownership instructions. Do not publish `.venv`, local SQLite data, secrets, or claim the localhost URL is publicly accessible.
