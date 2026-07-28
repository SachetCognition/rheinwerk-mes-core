"""Shared arrangement helpers for the W2-1/2/3 acceptance suites (URS-W2-001…012).

Not a test module: the `test_w2_genealogy_*` and `test_w2_batch_*` suites share these
posting helpers so `tests/conftest.py` stays untouched for the parallel wave children
(same convention as `test_w1_gating_support.py`).
"""

from __future__ import annotations

from typing import Any

import pytest

COMPANY = "Rheinwerk Chemie GmbH"
RM_WAREHOUSE = "RM Lager Nord - RWC"
FG_WAREHOUSE = "FG Lager Süd - RWC"
RECIPE = "BOM-RW-CHM-0003-001"

RAW_ITEM = "RW-CHM-0001"
ADDITIVE_ITEM = "RW-CHM-0002"
COMPOUND_ITEM = "RW-CHM-0003"

BATCH_A1 = "BATCH-A-0001"
BATCH_A2 = "BATCH-A-0002"
BATCH_C1 = "BATCH-C-1001"
BATCH_C2 = "BATCH-C-1002"
SUPPLIER_BATCH = "SUP-K7-0001"

FIRST_ORDER = "PO-2026-0001"
SECOND_ORDER = "PO-2026-0002"
THIRD_ORDER = "PO-2026-0003"

QUARANTINE_LOCATION = "NORD-Q-01"
STORAGE_LOCATION = "NORD-A-01-01"

#: Inside the shelf life of every fixture batch, so the W1 expiry hard stop does not fire
#: while a W2 case arranges its postings (URS-W1-013).
POSTING_DATE = "2026-04-20"


def require_fixture(site: Any, doctype: str, name: str) -> Any:
	"""Return a seeded programme fixture, skipping when the site was not seeded."""
	if not site.db.exists(doctype, name):
		pytest.skip(f"programme fixture {doctype} {name} not seeded on this site")
	return site.get_doc(doctype, name)


def require_w2_schema(site: Any) -> None:
	"""Skip when `rheinwerk_mes.setup.w2_genealogy` has not run on this site."""
	if not site.get_meta("Batch").get_field("qa_state"):
		pytest.skip("W2 canonical-batch custom fields not installed on this site")


def new_work_order(site: Any, qty: float = 10.0) -> str:
	"""A fresh draft work order — a case posts against it without touching the fixtures."""
	doc = site.get_doc(
		{
			"doctype": "Work Order",
			"company": COMPANY,
			"production_item": COMPOUND_ITEM,
			"bom_no": RECIPE,
			"qty": qty,
			"stock_uom": "Kg",
			"wip_warehouse": RM_WAREHOUSE,
			"fg_warehouse": FG_WAREHOUSE,
			"planned_start_date": f"{POSTING_DATE} 08:00:00",
			"planned_end_date": f"{POSTING_DATE} 16:00:00",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def post_consumption(
	site: Any,
	work_order: str,
	rows: list[tuple[str, str | None, float]],
	posting_date: str = POSTING_DATE,
	submit: bool = True,
) -> Any:
	"""Post a batch-aware consumption of `work_order` (`(item, batch, qty)` rows)."""
	doc = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": COMPANY,
			"work_order": work_order,
			"set_posting_time": 1,
			"posting_date": posting_date,
			"posting_time": "08:00:00",
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"s_warehouse": RM_WAREHOUSE,
					"uom": "Kg",
					"use_serial_batch_fields": 1 if batch else 0,
					"batch_no": batch,
				}
				for item, batch, qty in rows
			],
		}
	)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def post_output(
	site: Any,
	work_order: str,
	batch: str,
	qty: float,
	item: str = COMPOUND_ITEM,
	posting_date: str = POSTING_DATE,
) -> Any:
	"""Record the produced batch of `work_order` (creates the batch when new)."""
	if not site.db.exists("Batch", batch):
		site.get_doc(
			{
				"doctype": "Batch",
				"batch_id": batch,
				"item": item,
				"manufacturing_date": posting_date,
				"expiry_date": "2027-12-31",
				"qty_original": qty,
			}
		).insert(ignore_permissions=True)
	doc = site.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"work_order": work_order,
			"set_posting_time": 1,
			"posting_date": posting_date,
			"posting_time": "09:00:00",
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"t_warehouse": FG_WAREHOUSE,
					"uom": "Kg",
					"basic_rate": 5.0,
					"use_serial_batch_fields": 1,
					"batch_no": batch,
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def set_state(site: Any, batch: str, state: str) -> None:
	"""Arrange a `qa_state` directly (arrangement only — never the act under test)."""
	site.db.set_value("Batch", batch, "qa_state", state, update_modified=False)
