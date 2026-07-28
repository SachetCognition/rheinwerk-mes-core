# ADR-011: Naming and numbering scheme (W0-8, URS-W0-014)
- **Status:** Proposed (sign-off required before W0 exit)
- **Context:** Plant A (Qcadoo) generates primary identifiers in the database: `mes_db_en.sql:1044` and `:1140-1183` install triggers that build order and batch numbers from PostgreSQL sequences, so the number is a property of the schema and cannot be reproduced by an application layer. ERPNext instead names documents through Frappe naming series evaluated in the application (dossier ch. 3.2). Both estates carry numbers that appear on printed batch records and in customer correspondence, so identifiers already issued must stay resolvable after consolidation.
- **Decision:** Frappe naming series are canonical estate-wide; DB-trigger sequences are not reproduced. The registry lives in code (`rheinwerk_mes/setup/naming.py`), is applied by the idempotent installer, and is the single source every wave reads:

  | Entity | Series | Renders |
  |---|---|---|
  | Production order (anchor `Work Order`) | `PO-.YYYY.-.####.` | `PO-2026-0001` |
  | Batch (anchor `Batch`) | `BATCH-.{plant}.-.####.` | `BATCH-A-0001` |
  | Handling unit (`Handling Unit`, W2) | `HU-.####.` | `HU-0001` |

  Legacy trigger-generated numbers are **not** carried in the primary key. They are preserved as `legacy_refs` rows (child DocType `Legacy Ref`: source system, source entity, source identifier, migration timestamp) on the migrated record, e.g. Qcadoo order number `000123/2025` on `PO-2026-0001`, so every legacy number stays queryable and auditable.
- **Consequences:**
  - Numbering is platform-native: no database triggers, no cross-plant sequence collisions, and counters are visible/repairable through the Frappe `Series` table.
  - Legacy identifiers become searchable attributes rather than keys, so a record may hold several (Qcadoo *and* OFBiz) source identifiers — which the three-source consolidation requires.
  - A series is applied only once its DocType and every field it interpolates exist. In W0 that means the production-order series is live, while the batch series (needs the CDM-01 `plant` field) and the handling-unit series (needs the W2 `Handling Unit` DocType) are registered and asserted-by-preview only, and are applied by the wave that lands those entities. This keeps the decision in one place without W0 reaching into W1/W2 schema.
  - Interpretation: the format `{#}` in URS-W0-014 is read as the Frappe number placeholder and fixed at four digits (`.####.`), which is what makes the URS/TST fixture identifiers `PO-2026-0001` and `BATCH-A-0001` render exactly.
