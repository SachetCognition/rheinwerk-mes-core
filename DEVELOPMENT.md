# Development

`rheinwerk_mes` is a Frappe app installed on the ERPNext substrate. The anchor ERPNext
DocTypes are never forked — every absorbed behaviour is a `doc_event`, a gate callback or
a Custom Field this app owns.

## Local stack

| Component | Name | Notes |
|---|---|---|
| Bench | `~/frappe-bench` | override with `BENCH_PATH` |
| Substrate | `frappe`, `erpnext` (`SachetCognition/Chem_erpnext`, branch `develop`) | |
| This app | `rheinwerk_mes` | symlinked from the working tree into `frappe-bench/apps` |
| Site | `dev.localhost` | override with `FRAPPE_SITE` |

```bash
./scripts/setup_stack.sh     # site + substrate + app + assets + fixtures (idempotent)
./scripts/start_stack.sh     # http://dev.localhost:8000  (Administrator / admin)
```

`setup_stack.sh` honours `BENCH_PATH` (default `~/frappe-bench`), `FRAPPE_SITE`
(default `dev.localhost`), `DB_ROOT_PASSWORD` and `ERPNEXT_SRC`. Data is persistent in
MariaDB; Redis holds only cache and queues.

## Fixtures

```bash
cd ~/frappe-bench
bench --site dev.localhost execute rheinwerk_mes.fixtures.seed.seed_all
```

Seeds company "Rheinwerk Chemie GmbH" (abbr RWC), items RW-CHM-0001…0003, warehouses
RM Lager Nord / FG Lager Süd, production line LINE-1, `BOM-RW-CHM-0003-001` (governed and
Accepted) and production orders PO-2026-0001 / PO-2026-0002.

## Tests

Two suites run from the same `pytest tests` entrypoint:

* **offline** — pure-python parity contracts; no site needed (run in CI `ci.yml`).
* **site-backed** — integration/acceptance tests that request the `site` fixture and skip
  when no Frappe site is available (run in CI `server-tests.yml`).

```bash
# offline only
pytest tests -rs

# site-backed (needs the local stack running: mariadb + bench redis)
BENCH_PATH=~/frappe-bench FRAPPE_SITE=dev.localhost ~/frappe-bench/env/bin/python -m pytest tests -rs
```

## Lint

```bash
ruff check .
ruff format --check .
```
