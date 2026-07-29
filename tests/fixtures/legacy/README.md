# Legacy export fixtures

Committed master-data exports of the systems being consolidated, used by the migration
extractors and their tests.

- `ofbiz/plant-b-entities.xml` — Plant B, OFBiz entity-engine XML export subset
  (Product, GoodIdentification, FixedAsset, Facility); see `URS-W0-010`.

Fixtures are deliberately small and hand-curated: each one carries the edge cases its
requirement names, so a test failure points at a behaviour rather than at data volume.
