# Manual evidence register

Test cases whose verification cannot be a pytest — pipeline behaviour, for example — are
recorded here with their citation. The evidence-pack generator
(`python -m tools.evidence.generate --wave W{n}`) reads this table and reports those test
cases as **manual** evidence, so a pack never silently claims automated coverage.

Add a row only when the evidence genuinely exists and is citable. One row per test case.

| Test case | Evidence | Citation |
|---|---|---|
| TC-W0-003 | CI gates lint and test failures on every pull request (jobs `lint`, `tests`, `contracts`); a red-then-green pipeline pair is demonstrated in the W0-6/W0-7 pull request. | `.github/workflows/ci.yml` |
