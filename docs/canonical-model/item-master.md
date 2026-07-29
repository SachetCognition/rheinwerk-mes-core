# CDM-09 Item / Product master (URS-W0-003)

Canonical item master for all plants. The anchor ERPNext `Item` DocType is adopted as-is (dossier §5.2 — master data is Rich in all three sources, ERPNext richest); the only extension is the `legacy_refs` child table, added as a `rheinwerk_mes` Custom Field so the anchor is never forked.

**Fields:** anchor `Item` fields (`item_code`, `item_name`, `item_group`, `stock_uom`, `uoms` pack conversions, batch/shelf-life flags) **plus** integrity-layer extension `legacy_refs` (child DocType `Legacy Ref`: `source_system`, `source_entity`, `source_identifier`, `migrated_on`, `remarks`).

**Semantics:** `item_code` is the canonical, plant-independent identity issued by the target system; source-system identifiers are never carried in the primary key — they live in `legacy_refs`, one row per source record, so a Qcadoo product number, a legacy ERPNext `item_code` and an OFBiz `productId` can all resolve to one canonical item.

Source mapping legend: **=** direct, **≈** transform, **∅** no source equivalent (backfill/default), **✕** deliberately not carried.

| Canonical field | Qcadoo `basic_product` | ERPNext `Item` (legacy instance) | OFBiz `Product` |
|---|---|---|---|
| `item_code` | ≈ `number` (re-issued canonically; source number → `legacy_refs`) | ≈ `item_code` (re-issued canonically where it collides across plants) | ≈ `productId` |
| `item_name` | = `name` | = `item_name` | = `productName` |
| `description` | = `description` | = `description` | = `description` / `longDescription` |
| `item_group` | ≈ `category` | = `item_group` | ≈ `primaryProductCategoryId` |
| `stock_uom` | = `unit` | = `stock_uom` | = `quantityUomId` |
| `uoms` (pack conversions) | = `unitConversionItem` rows | = `uoms` | ≈ `ProductUomConversion` (global, narrowed to item level) |
| `has_batch_no` / `has_expiry_date` / `shelf_life_in_days` | ≈ implied by `Resource.expirationDate` usage | = `has_batch_no` / `has_expiry_date` / `shelf_life_in_days` | ≈ `lotIdFilledIn`, `shelfLifeInDays` |
| `is_stock_item` | ∅ (all products are stocked) | = `is_stock_item` | ≈ `isPhysical` / `productTypeId` |
| `legacy_refs.source_identifier` | = `number` (e.g. `P-000123`) | = `item_code` (e.g. `COMPOUND-40`) | = `productId` (e.g. `RHEINOL-40-BASE`) |
| purchase/sales pricing | ✕ (group ERP owns pricing across the boundary) | ✕ | ✕ |

**Semantic-mismatch note:** "product" (Qcadoo, a production-planning master record) ≠ "Item" (ERPNext, a stock + costing master record) ≠ "Product" (OFBiz, a catalogue/commerce record with pricing and category trees). The canonical entity keeps only the manufacturing- and stock-relevant surface; commerce attributes stay with the group ERP.

**Fixtures:** RW-CHM-0001 "Rheinol 40 Basisharz" (kg, 1 sack = 25 kg), RW-CHM-0002 "Additiv K7" (kg, 1 pail = 5 kg), RW-CHM-0003 "Rheinol 40 Compound" (kg) — seeded by `rheinwerk_mes.fixtures.seed.seed_all`, verified by TC-W0-004.
