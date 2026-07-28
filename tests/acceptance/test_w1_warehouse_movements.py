"""W1-5 batch-aware stock movements on the anchor ledger.

TC-W1-022 (URS-W1-021) — Qcadoo document types map to anchor Stock Entry purposes, every
    movement carries a batch allocation, and history lives only on the Stock Ledger (no
    parallel quantity store).
"""

from __future__ import annotations

STOCK_ENTRY_PURPOSE = "rheinwerk_mes.warehouse.movements.stock_entry_purpose"
BOOK_MOVEMENT = "rheinwerk_mes.warehouse.movements.book_movement"
LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"

COMPANY = "Rheinwerk Chemie GmbH"
RM = "RM Lager Nord - RWC"


def test_tc_w1_022_document_types_map_to_stock_entry_purposes(site):
	"""TC-W1-022 (URS-W1-021): the Qcadoo document taxonomy maps onto anchor Stock Entry
	purposes (Receipt→Material Receipt, Release→Material Issue, Transfer→Material Transfer)."""
	stock_entry_purpose = site.get_attr(STOCK_ENTRY_PURPOSE)
	assert stock_entry_purpose("RECEIPT") == "Material Receipt"
	assert stock_entry_purpose("RELEASE") == "Material Issue"
	assert stock_entry_purpose("TRANSFER") == "Material Transfer"


def test_tc_w1_022_batch_aware_receipt_and_issue_hit_only_the_ledger(site):
	"""TC-W1-022 (URS-W1-021): a batch-aware receipt then issue post as anchor Stock
	Entries with the batch allocated and the storage location referenced; the resulting
	balance is read back from the Stock Ledger, the single quantity source."""
	book_movement = site.get_attr(BOOK_MOVEMENT)
	ledger_balance = site.get_attr(LEDGER_BALANCE)

	site.get_doc(
		{
			"doctype": "Batch",
			"batch_id": "BATCH-MOVE-01",
			"item": "RW-CHM-0002",
			"expiry_date": "2027-12-31",
			"manufacturing_date": "2026-05-01",
		}
	).insert(ignore_permissions=True)

	before = ledger_balance("RW-CHM-0002", RM, "BATCH-MOVE-01")

	receipt = book_movement(
		document_type="RECEIPT",
		item="RW-CHM-0002",
		qty=120,
		batch_no="BATCH-MOVE-01",
		company=COMPANY,
		target_warehouse=RM,
		storage_location="NORD-A-01-01",
		basic_rate=3.0,
	)
	assert site.db.get_value("Stock Entry", receipt, "purpose") == "Material Receipt"
	assert ledger_balance("RW-CHM-0002", RM, "BATCH-MOVE-01") == before + 120

	issue = book_movement(
		document_type="RELEASE",
		item="RW-CHM-0002",
		qty=20,
		batch_no="BATCH-MOVE-01",
		company=COMPANY,
		source_warehouse=RM,
	)
	assert site.db.get_value("Stock Entry", issue, "purpose") == "Material Issue"
	assert ledger_balance("RW-CHM-0002", RM, "BATCH-MOVE-01") == before + 100
