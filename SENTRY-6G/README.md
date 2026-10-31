# SENTRY-6G

**AIORI-3 · PS-021 — Experimental Dialog Correlation and Recovery Across Agent Adapters**

SENTRY-6G is a runnable prototype for tracking operations across two mock agent adapters and recovering safely when acknowledgements or connections fail. It maintains a consistent dialog identity, records lifecycle changes, checks executor-side evidence, and prevents duplicate simulated effects when the same operation is delivered more than once.

The system uses local HTTP services, FastAPI, and SQLite. It demonstrates recovery behaviour under controlled fault simulations; it does not communicate with a real 6G network or modify production network equipment.

## What the prototype does

- Assigns a persistent dialog ID and links the requester's ID, executor-side ID, and operation ID.
- Tracks explicit dialog states: `CREATED`, `DISPATCHED`, `UNCERTAIN`, `COMPLETED`, and `ESCALATED`.
- Records dialog transitions and evidence checks in a SQLite event journal.
- Uses executor-side idempotency to avoid applying the same simulated operation twice.
- Reconciles uncertain outcomes against the executor's independent effect ledger rather than blindly repeating the operation.
- Provides a browser dashboard, HTTP APIs, automated tests, and a repeatable five-scenario demonstration.

## Architecture

The prototype consists of three local HTTP services:

**Requester — Adapter A (`localhost:8000`)**  
Accepts an operation request and forwards it to the coordinator through `POST /delegate`.

**Coordinator (`localhost:8001`)**  
Creates and tracks dialogs, records state transitions, and performs evidence-based recovery. It also serves the dashboard and the main inspection APIs.

**Executor — Adapter B (`localhost:8002`)**  
Applies simulated operations and stores their results in an independent SQLite ledger. The effect record also acts as the idempotency record, and both are handled within the same database transaction.

```text
Requester (8000)  --->  Coordinator (8001)  --->  Executor (8002)
                             |                         |
                       Dialog journal             Effect ledger
                         (SQLite)                   (SQLite)
                             |                         |
                             +---- Evidence query <----+
```

The coordinator stores `data/coordinator.db`; the executor stores `data/executor.db`. Database files are created locally when the services start and should not be committed to the repository.

### Recovery decisions

- **`VERIFIED_DONE`** — The executor ledger contains the operation. The coordinator can mark the dialog `COMPLETED`.
- **`VERIFIED_NOT_EXECUTED`** — No matching operation is present in the simulated executor ledger at the time of the query. The current implementation does not automatically dispatch the operation again or mark the dialog completed.
- **`UNKNOWN`** — The coordinator cannot establish the outcome, such as when the executor is unreachable. The dialog remains uncertain until further evidence is available.

The executor ledger is authoritative only for the simulated operations in this prototype. Ledger absence is not proof that an arbitrary external action never happened.

## Requirements

- Python **3.10 or newer** (locally tested with Python 3.10.11)
- Windows PowerShell, Linux, or macOS
- Three available local ports: **8000**, **8001**, and **8002**

The project does not require Node.js, Docker, or an external database server.

## Installation

Clone the official repository and open the application directory:

```bash
git clone https://github.com/aiori-hackathon/A3-PS021-TC509.git
cd A3-PS021-TC509/SENTRY-6G
```

**Windows PowerShell**

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Linux / macOS**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If Python 3.10 is unavailable, use another installed supported Python version to create the environment.

## Running the system

Open three terminals in the `SENTRY-6G` directory. Start the services in this order:

**Terminal 1 — Executor**

```powershell
.\.venv\Scripts\python.exe service.py executor
```

**Terminal 2 — Coordinator and dashboard**

```powershell
.\.venv\Scripts\python.exe service.py coordinator
```

**Terminal 3 — Requester**

```powershell
.\.venv\Scripts\python.exe service.py requester
```

On Linux/macOS, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

Open the dashboard at **http://127.0.0.1:8001/**. Interactive API documentation is available at `http://127.0.0.1:8000/docs`, `http://127.0.0.1:8001/docs`, and `http://127.0.0.1:8002/docs`.

These are **local addresses**, not public live-demo links.

## Fault scenarios

The dashboard and demo script support five controlled scenarios:

1. **Lost acknowledgement (`lost_ack`)** — The executor commits the simulated operation, but the acknowledgement is treated as lost. The coordinator initially records `UNCERTAIN`; recovery checks the executor ledger and resolves the dialog to `COMPLETED`.
2. **Duplicate delivery (`duplicate`)** — The same operation is submitted twice to the executor. The second attempt is identified as a duplicate, and only one effect record is created.
3. **Partition before dispatch (`partition`)** — The coordinator simulates an interruption before sending the operation. The dialog becomes `UNCERTAIN`. A subsequent ledger check returns `VERIFIED_NOT_EXECUTED`, but the coordinator does not automatically retry or complete the dialog.
4. **Delayed response (`delay`)** — The coordinator introduces a configurable delay before dispatch. The operation can still complete normally.
5. **Restart-related uncertainty (`restart`)** — The automated scenario models a lost acknowledgement and subsequent recovery. **It does not restart a running process.** Actual restart persistence can be demonstrated manually by restarting the coordinator and checking the retained dialog records.

These faults are injected in application logic. They are not measurements from a real impaired wireless network.

## Tests and reproducible demo

With the environment installed, run the automated tests from the application directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

For the five-scenario demo, start the executor and coordinator first, then run:

```powershell
.\.venv\Scripts\python.exe judge_demo.py
```

On Linux/macOS, use `.venv/bin/python` in both commands.

The demo submits a fresh request for each scenario, checks the final dialog state and executor evidence, and compares the change in the executor's effect count with the expected count. It writes timestamped **JSON** and **Markdown** reports to `reports/`.

**Local validation (31 October 2026):** The team observed **11/11 passing automated tests** and **five passing demo scenarios**. In that demo run, the executor ledger increased by **4 effects**, matching the expected four executed operations; the partition scenario produced no effect. These results describe the local mock environment and should not be interpreted as 6G-network performance measurements.

### Checking persistence across an actual coordinator restart

1. Start all three services and create a dialog through the dashboard.
2. Note its `dialog_id` and current state.
3. Stop **only** the coordinator service (`Ctrl+C` in its terminal).
4. Restart it with `service.py coordinator`.
5. Open `http://127.0.0.1:8001/dialogs` and verify that the dialog ID and recorded state are retained.
6. For an uncertain dialog, call `POST /recover/{dialog_id}` or use the dashboard's recovery action to query executor evidence.

The coordinator's SQLite journal survives the process restart. The dashboard's last-selected dialog is browser state and may need to be selected again.

## API reference

**Requester — port 8000**

- `POST /delegate` — Forward a request to the coordinator.
- `GET /health` — Check requester health.

**Coordinator — port 8001**

- `POST /submit` — Create or reuse a dialog and process an operation.
- `POST /recover/{dialog_id}` — Reconcile a dialog using executor evidence.
- `GET /dialogs` — List recorded dialogs.
- `GET /events` — Inspect recent journal events.
- `GET /stats` — View dialog counts and, when available, executor effect counts.
- `GET /audit/{op_id}` — Retrieve executor evidence for an operation.
- `GET /executor-health` — Check executor connectivity.
- `GET /network-policy` — Return an experimental waiting-time recommendation.
- `GET /` — Open the dashboard.

**Executor — port 8002**

- `POST /execute` — Apply or deduplicate a simulated operation.
- `GET /status/{op_id}` — Return executor-side evidence.
- `GET /effects` — Return the number of stored simulated effects.

Example request using PowerShell:

```powershell
$body = @{ a_id = 'demo-001'; command = 'QoS=high'; fault = 'lost_ack' } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/delegate' -Method Post -ContentType 'application/json' -Body $body
```

The `a_id` identifies a requester operation. Reusing the same `a_id` with a different command is rejected; use a fresh ID for each independent demo request.

## Repository layout

```text
SENTRY-6G/
├── core.py                  SQLite persistence, dialog states, and effect ledger
├── service.py               Requester, coordinator, and executor services
├── judge_demo.py            Five-scenario local validation and report export
├── requirements.txt         Python dependencies
├── web/
│   └── index.html           Browser dashboard
└── tests/
    ├── test_core.py         Persistence, state, and idempotency tests
    └── test_api_metrics.py  API and metrics tests
```

Runtime SQLite files are stored under `data/`; generated demo reports are stored under `reports/`.

## Implementation boundaries

SENTRY-6G is an experimental adapter and recovery prototype, not a complete MCP/A2A interoperability implementation or a final IETF protocol implementation. It does not guarantee exactly-once delivery across arbitrary external systems. Its duplicate-effect protection applies to the simulated executor's transactional SQLite ledger.

The `network-policy` endpoint provides a heuristic waiting-time suggestion; it is not a trained or empirically validated adaptive scheduler. The current evaluation does not include a comparative baseline or performance claims against alternative recovery systems. APIs are intended for local demonstration and have no production authentication or deployment hardening.

The project illustrates how persistent identity, explicit uncertainty, and executor-side evidence can support safer recovery decisions across independent mock adapters.
