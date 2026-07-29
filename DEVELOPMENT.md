# Development stack

The consolidated MES is a Frappe app (`rheinwerk_mes`) installed **alongside** the
ERPNext substrate on one site — the two-app packaging ratified in
`ARCHITECTURE.md` ("the base is consumed as an upstream dependency; all Rheinwerk
behaviour lives in the `rheinwerk_mes` app"). Anchor DocTypes are never forked.

| Layer | Source | Notes |
|---|---|---|
| Framework | Frappe `develop` | MariaDB + Redis, persistent MariaDB data directory |
| Substrate app | `SachetCognition/Chem_erpnext` (`develop`) | ERPNext, installed unmodified |
| This app | `rheinwerk_mes` | symlinked from the working tree into `frappe-bench/apps` |

## Build and run

```bash
./scripts/setup_stack.sh     # site + substrate + app + assets (idempotent)
./scripts/start_stack.sh     # serve http://dev.localhost:8000  (Administrator / admin)
```

`setup_stack.sh` honours `BENCH_PATH` (default `~/frappe-bench`), `FRAPPE_SITE`
(default `dev.localhost`), `DB_ROOT_PASSWORD` (default `frappe`) and
`ERPNEXT_SRC` (default `~/repos/Chem-erpnext`, falling back to the GitHub remote).

Data survives restarts: the site database lives in MariaDB's data directory and
site files in `frappe-bench/sites/<site>`; Redis holds only cache and queues.

## Test suites

```bash
# offline: repo-structure checks (no site required)
pytest tests

# site-backed: same command with a site present; the `site` fixture connects to it
BENCH_PATH=~/frappe-bench FRAPPE_SITE=dev.localhost ~/frappe-bench/env/bin/python -m pytest tests
```

* `tests/acceptance/` — per-wave target-state journeys mapped 1:1 to the TC IDs in
  `docs/test/TST-W{n}-*.md`. `test_w0_scaffold.py` covers TC-W0-001 / TC-W0-002.
* `tests/characterisation/` — executable Qcadoo parity contracts (added in W0-6).

Site-backed tests skip (never fail) when no site is reachable, so `pytest tests`
is safe on a bare checkout.

## Lint

```bash
ruff check . && ruff format --check .
```
