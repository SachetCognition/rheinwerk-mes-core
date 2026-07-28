"""TC-W2-007 / TC-W2-008 / TC-W2-011 / TC-W2-012 — the canonical Batch (W2-2).

Verifies **URS-W2-005 AC-1…3** (identity/expiry/qa_state facets on the anchor Batch, expiry
mandatory for shelf-life items, anchor DocType not forked), **URS-W2-007 AC-1/AC-2** (the W0
`legacy_refs` child table is the single legacy-identifier store) and **URS-W2-008 AC-1**
(canonical expiry drives the FEFO proposal).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_w2_genealogy_support import (
	BATCH_A1,
	BATCH_A2,
	RAW_ITEM,
	RM_WAREHOUSE,
	require_fixture,
	require_w2_schema,
)

frappe = pytest.importorskip("frappe")
disposal = pytest.importorskip("rheinwerk_mes.warehouse.disposal")
qa_state = pytest.importorskip("rheinwerk_mes.genealogy.qa_state")


def test_canonical_batch_carries_identity_expiry_and_disposition(site):
	"""URS-W2-005 AC-1 / TC-W2-007 step 1 — all four facets on one record."""
	require_w2_schema(site)
	name = "BATCH-A-9001"
	site.get_doc(
		{
			"doctype": "Batch",
			"batch_id": name,
			"item": RAW_ITEM,
			"qty_original": 500.0,
			"stock_uom": "Kg",
			"supplier_batch_no": "LF-2026-77",
			"manufacturing_date": "2026-01-05",
			"expiry_date": "2026-12-31",
		}
	).insert(ignore_permissions=True)

	doc = site.get_doc("Batch", name)
	assert (doc.batch_id, doc.item, doc.qty_original) == (name, RAW_ITEM, 500.0)
	assert doc.supplier_batch_no == "LF-2026-77"
	assert frappe.utils.formatdate(doc.expiry_date, "dd.MM.yyyy") == "31.12.2026"
	assert doc.qa_state == qa_state.QUARANTINED, "every new batch enters Quarantined"
	assert doc.meta.has_field("genealogy_links") and doc.meta.has_field("legacy_refs")


def test_shelf_life_item_without_expiry_is_refused(site):
	"""URS-W2-005 AC-2 / TC-W2-007 step 2 — the save is refused naming the expiry date."""
	require_w2_schema(site)
	item = "RW-CHM-9002"
	if not site.db.exists("Item", item):
		site.get_doc(
			{
				"doctype": "Item",
				"item_code": item,
				"item_name": "Kurzläufer-Harz",
				"item_group": "Raw Material",
				"stock_uom": "Kg",
				"has_batch_no": 1,
				"has_expiry_date": 1,
				"shelf_life_in_days": 0,
			}
		).insert(ignore_permissions=True)

	with pytest.raises(frappe.ValidationError) as refusal:
		site.get_doc({"doctype": "Batch", "batch_id": "BATCH-X-0001", "item": item}).insert(
			ignore_permissions=True
		)

	assert "Expiry" in str(refusal.value) or "Verfall" in str(refusal.value)


def test_anchor_batch_doctype_is_not_forked(site, repo_root):
	"""URS-W2-005 AC-3 / TC-W2-008 — extensions exist only as Custom Fields."""
	require_w2_schema(site)
	anchor_json = Path(frappe.get_app_path("erpnext", "stock", "doctype", "batch", "batch.json"))
	upstream = json.loads(anchor_json.read_text(encoding="utf-8"))
	upstream_fields = {field["fieldname"] for field in upstream["fields"]}

	standard = {
		field.fieldname for field in site.get_meta("Batch").fields if not getattr(field, "is_custom_field", 0)
	}
	assert standard == upstream_fields, "no core field added, removed or renamed"

	extensions = set(site.get_all("Custom Field", filters={"dt": "Batch"}, pluck="fieldname"))
	assert {"qa_state", "genealogy_links", "legacy_refs"} <= extensions
	assert not (repo_root / "rheinwerk_mes/genealogy/doctype/batch").exists(), "no forked Batch"


def test_legacy_refs_are_preserved_verbatim_in_the_w0_child_table(site):
	"""URS-W2-007 AC-1 / TC-W2-011 step 1 — both merged legacy identifiers survive."""
	require_w2_schema(site)
	doc = require_fixture(site, "Batch", BATCH_A1)
	doc.append("legacy_refs", {"source_system": "Qcadoo", "source_identifier": "GB-4711"})
	doc.append("legacy_refs", {"source_system": "Qcadoo", "source_identifier": "RB-4711"})
	doc.save(ignore_permissions=True)

	stored = [row.source_identifier for row in site.get_doc("Batch", BATCH_A1).legacy_refs]
	assert stored == ["GB-4711", "RB-4711"], "identifiers verbatim, one single store"
	assert not site.get_meta("Batch").get_field("legacy_batch_no"), "no second legacy store"


def test_fefo_proposal_orders_by_canonical_expiry(site):
	"""URS-W2-008 AC-1 / TC-W2-012 step 1 — the earlier canonical expiry is proposed first."""
	require_w2_schema(site)
	require_fixture(site, "Batch", BATCH_A1)
	require_fixture(site, "Batch", BATCH_A2)

	proposal = disposal.picking_order_for_warehouse(RAW_ITEM, RM_WAREHOUSE)

	assert disposal.warehouse_algorithm(RM_WAREHOUSE) == "FEFO"
	assert proposal.index(BATCH_A2) < proposal.index(BATCH_A1), "30.06.2026 before 31.12.2026"
