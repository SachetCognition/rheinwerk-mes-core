# Development stack

The consolidated MES is a Frappe app (`rheinwerk_mes`) installed **alongside** the
ERPNext substrate on one site — the two-app packaging ratified in
`docs/target-model/base-repo-decision.md` ("the base is consumed as an upstream
dependency; all Rheinwerk behaviour lives in the `rheinwerk_mes` app"). Anchor
DocTypes are never forked.

| Layer | Source | Notes |
|---|---|---|
| Framework | Frappe `develop` | MariaDB + Redis, persistent MariaDB data directory |
| Substrate app | `SachetCognition/Chem_erpnext` (`develop`) | ERPNext, installed unmodified |
| This app | `rheinwerk_mes` | symlinked from the working tree into `frappe-bench/apps` |

## Build and run

```bash
./scripts/setup_stack.sh     # site + substrate + app + assets + fixtures (idempotent)
./scripts/start_stack.sh     # serve http://dev.localhost:8000  (Administrator / admin)
```

`setup_stack.sh` honours `BENCH_PATH` (default `~/frappe-bench`), `FRAPPE_SITE`
(default `dev.localhost`), `DB_ROOT_PASSWORD` (default `frappe`) and
`ERPNEXT_SRC` (default `~/repos/Chem-erpnext`, falling back to the GitHub remote).

Data survives restarts: the site database lives in MariaDB's data directory and
site files in `frappe-bench/sites/<site>`; Redis holds only cache and queues.

## Fixture seeding

```bash
cd ~/frappe-bench
bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all
```

Seeds the shared programme fixtures from `docs/test/TST-W0-foundation.md` §1
(company Rheinwerk Chemie GmbH, UoMs + conversions, items RW-CHM-0001…0003,
warehouses RM Lager Nord / FG Lager Süd, work centres LINE-1/MIX-01 and
LINE-1/FILL-01, the six personas). Re-running is safe.

## Test suites

```bash
# offline: parity contracts + repo-structure checks (no site required)
pytest tests

# site-backed: same command with a site present; the `site` fixture connects to it
BENCH_PATH=~/frappe-bench FRAPPE_SITE=dev.localhost ~/frappe-bench/env/bin/python -m pytest tests
```

* `tests/characterisation/` — executable Qcadoo parity contracts (the regression
  floor; a failing contract fails CI).
* `tests/acceptance/` — per-wave target-state journeys mapped 1:1 to the TC IDs in
  `docs/test/TST-W{n}-*.md`.

Site-backed tests skip (never fail) when no site is reachable, so `pytest tests`
is safe on a bare checkout; the `Server tests` workflow runs them for real.

## Lint

```bash
ruff check . && ruff format --check .
```

## CI

* `.github/workflows/ci.yml` — lint + offline suites on every PR.
* `.github/workflows/server-tests.yml` — builds the full stack, seeds fixtures and
  runs the site-backed suites (the regression floor required by EXIT-W0-3).
