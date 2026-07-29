# Test suites

- `characterisation/` — legacy behaviour pins for the five core journeys per source system (regression floor; W0)
- `acceptance/` — target-state journey tests per wave; every deliberate behaviour change vs legacy is flagged for business sign-off

Run the suites the way CI does (`.github/workflows/ci.yml`):

```bash
# from the repository root
pip install -r requirements-dev.txt
pytest tests -rs
```
