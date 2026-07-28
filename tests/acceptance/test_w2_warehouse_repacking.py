"""W2-8 repacking journey — split across handling units, preserving ledger truth.

TC-W2-035 (URS-W2-027) — repacking 100 kg of BATCH-A-0001 from one Handling Unit to
    another leaves the handling units referencing 400/100 kg with the batch identity
    unchanged and the ledger untouched (AC-1); a deliberate new-lot repack mints a Batch
    carrying `parent_batch = BATCH-A-0001` (split lineage, distinct from production
    genealogy) while the item's on-hand total is unchanged — no quantity invented or lost
    (AC-2).
"""

from __future__ import annotations

COMPANY = "Rheinwerk Chemie GmbH"
RM = "RM Lager Nord - RWC"
ITEM = "RW-CHM-0001"
BATCH = "BATCH-A-0001"
LOCATION = "NORD-A-01-01"

LEDGER_BALANCE = "rheinwerk_mes.warehouse.availability.ledger_balance"
SPLIT_LINEAGE = "rheinwerk_mes.warehouse.repacking.split_lineage"
LINKS_OF = "rheinwerk_mes.genealogy.links.links_of"


def _pallet(site, qty: float | None):
	contents = [{"item": ITEM, "batch_no": BATCH, "qty": qty, "uom": "Kg"}] if qty else []
	return site.get_doc(
		{
			"doctype": "Handling Unit",
			"hu_type": "Palette",
			"warehouse": RM,
			"storage_location": LOCATION,
			"company": COMPANY,
			"contents": contents,
		}
	).insert(ignore_permissions=True)


def _hu_qty(site, hu: str, item: str, batch: str | None) -> float:
	doc = site.get_doc("Handling Unit", hu)
	return sum(
		row.qty for row in doc.contents if row.item == item and (row.batch_no or None) == (batch or None)
	)


def _accept_repack(site, **kwargs):
	doc = site.get_doc(
		{
			"doctype": "Repacking",
			"warehouse": RM,
			"company": COMPANY,
			"item": ITEM,
			"batch_no": BATCH,
			"uom": "Kg",
			**kwargs,
		}
	).insert(ignore_permissions=True)
	doc.state = "Accepted"
	doc.save()
	doc.reload()
	return doc


def test_tc_w2_035_same_identity_repack_moves_reference_only(site):
	"""TC-W2-035 (URS-W2-027 AC-1): repacking 100 kg of BATCH-A-0001 from HU-source to
	HU-target leaves the units at 400/100 kg, the batch identity unchanged, and the anchor
	ledger balance of the batch untouched — a Handling Unit is only a reference layer."""
	ledger_balance = site.get_attr(LEDGER_BALANCE)
	source = _pallet(site, 500)
	target = _pallet(site, None)
	before = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))

	doc = _accept_repack(
		site,
		source_handling_unit=source.name,
		target_handling_unit=target.name,
		qty=100,
	)

	assert doc.state == "Accepted"
	assert _hu_qty(site, source.name, ITEM, BATCH) == 400.0
	assert _hu_qty(site, target.name, ITEM, BATCH) == 100.0
	# Same batch identity, ledger untouched: the reference split invents no quantity.
	assert float(ledger_balance(ITEM, RM, BATCH, consider_expired=True)) == before


def test_tc_w2_035_new_lot_repack_sets_parent_batch_and_keeps_ledger_consistent(site):
	"""TC-W2-035 (URS-W2-027 AC-2): a deliberate new-lot repack of 100 kg mints a Batch with
	`parent_batch = BATCH-A-0001`; the source batch drops by 100 kg and the new batch gains
	100 kg, so the item's on-hand total is unchanged. The split lineage is distinct from
	production genealogy — the repack writes no Genealogy Link."""
	ledger_balance = site.get_attr(LEDGER_BALANCE)
	split_lineage = site.get_attr(SPLIT_LINEAGE)
	links_of = site.get_attr(LINKS_OF)

	source = _pallet(site, 500)
	target = _pallet(site, None)
	item_total_before = float(ledger_balance(ITEM, RM, consider_expired=True))
	source_batch_before = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))

	doc = _accept_repack(
		site,
		source_handling_unit=source.name,
		target_handling_unit=target.name,
		qty=100,
		creates_new_lot=1,
	)

	new_batch = doc.new_batch
	assert new_batch
	assert site.db.get_value("Batch", new_batch, "parent_batch") == BATCH

	source_after = float(ledger_balance(ITEM, RM, BATCH, consider_expired=True))
	new_after = float(ledger_balance(ITEM, RM, new_batch, consider_expired=True))
	assert source_after == source_batch_before - 100.0
	assert new_after == 100.0
	# Ledger consistency: quantity only changed identity, the item total is unchanged.
	assert float(ledger_balance(ITEM, RM, consider_expired=True)) == item_total_before

	lineage = split_lineage(new_batch)
	assert lineage["parents"] == [BATCH]
	assert lineage["is_split"] is True
	# Split lineage is distinct from production genealogy: no Genealogy Link is written.
	assert links_of(new_batch) == []
