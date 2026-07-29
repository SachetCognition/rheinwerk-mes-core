# Test suites

- `characterisation/` — legacy behaviour pins for the five core journeys per source system (regression floor; W0). Executable parity contracts, offline (no Frappe site): `pytest tests/characterisation`. See `characterisation/README.md`
- `acceptance/` — target-state journey tests per wave; every deliberate behaviour change vs legacy is flagged for business sign-off
