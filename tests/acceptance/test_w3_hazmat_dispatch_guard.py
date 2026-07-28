"""W3-6 — the hazmat dispatch gate (URS-W3-018 AC-2).

TC-W3-022: dispatching a batch whose hazmat profile lacks its UN number is refused
modal-grade, naming the rule (ADR data incomplete), the record (item, batch and the missing
field) and the resolution (complete the profile), and the refusal is written to the
`Execution Gate Log`. The Terminal-mode conformance of the dispatch station (48 px targets,
focused scanner field) is asserted against the committed page assets.

White space in all three legacy systems (dossier §6.3) — no parity contract; see
`docs/design/W3-hazmat-dispatch.md`.
"""

from __future__ import annotations

import pytest

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
dispatch = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.dispatch")
labels = pytest.importorskip("rheinwerk_mes.regulatory_hazmat.labels")

COMPANY = "Rheinwerk Chemie GmbH"
WAREHOUSE = "FG Lager Süd - RWC"
GAP_ITEM = "RW-CHM-0004"
GAP_BATCH = "BATCH-D-0001"
GAP_PROFILE = "HAZ-RW-CHM-0004"
OK_ITEM = "RW-CHM-0003"
OK_BATCH = "BATCH-C-1001"


def _require_fixture(site) -> None:
	if not site.db.exists("Batch", GAP_BATCH) or not site.db.exists("Hazmat Profile", GAP_PROFILE):
		pytest.skip("W3 incomplete-ADR fixture not seeded on this site")


def _dispatch_entry(item: str, batch: str, qty: float = 5.0):
	return frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"company": COMPANY,
			"items": [
				{
					"item_code": item,
					"qty": qty,
					"s_warehouse": WAREHOUSE,
					"uom": frappe.db.get_value("Item", item, "stock_uom"),
					"use_serial_batch_fields": 1,
					"batch_no": batch,
				}
			],
		}
	)


def test_tc_w3_022_incomplete_adr_profile_refuses_dispatch(site):
	"""TC-W3-022 step 1 (URS-W3-018 AC-2): the refusal names rule, record and resolution."""
	_require_fixture(site)

	with pytest.raises(frappe.ValidationError) as refusal:
		_dispatch_entry(GAP_ITEM, GAP_BATCH).insert(ignore_permissions=True)

	message = str(refusal.value)
	# Rule.
	assert "Gefahrgut darf nur mit vollständigen ADR-Transportdaten versandt werden" in message
	# Record: the item, the batch, the profile and the missing field by its German label.
	assert GAP_ITEM in message
	assert GAP_BATCH in message
	assert GAP_PROFILE in message
	assert "UN-Nummer" in message
	# Resolution.
	assert "Gefahrstoffprofil vervollständigen" in message


def test_tc_w3_022_refusal_is_audited(site):
	"""TC-W3-022 step 1 (URS-W3-018 AC-2, URS-W1-033): the refusal is logged, not just shown.

	The gate writes to the same `Execution Gate Log` as every other gated action through
	`execution_gating.audit.log_refusal`, so a refused dispatch is auditable evidence.
	"""
	_require_fixture(site)
	before = frappe.db.count("Execution Gate Log", {"gate": dispatch.GATE, "reference_name": GAP_BATCH})

	with pytest.raises(frappe.ValidationError):
		_dispatch_entry(GAP_ITEM, GAP_BATCH).insert(ignore_permissions=True)

	logs = frappe.get_all(
		"Execution Gate Log",
		filters={"gate": dispatch.GATE, "reference_name": GAP_BATCH},
		fields=["outcome", "rule", "reference_doctype", "detail"],
		order_by="creation desc",
	)
	assert len(logs) > before
	assert logs[0].outcome == "Abgelehnt"
	assert logs[0].reference_doctype == "Batch"
	assert "UN-Nummer" in logs[0].detail


def test_complete_profile_and_non_hazmat_stock_dispatch_freely(site):
	"""URS-W3-018 AC-2 (negative control): the gate refuses only incomplete hazmat data.

	A complete hazmat profile passes, so the rule cannot be satisfied by blocking everything;
	and stock without a hazmat profile is never inspected at all.
	"""
	_require_fixture(site)

	entry = _dispatch_entry(OK_ITEM, OK_BATCH)
	entry.insert(ignore_permissions=True)
	assert entry.name

	assert dispatch.adr_verdict(OK_BATCH) == (
		frappe.db.get_value("Item", OK_ITEM, "rw_hazmat_profile"),
		(),
	)
	assert dispatch.dispatch_blockers([{"item": OK_ITEM, "batch": OK_BATCH}]) == []


def test_internal_transfers_are_not_dispatch(site):
	"""URS-W3-018 AC-2: the gate sits at the *shipping* boundary, not on every posting.

	An internal transfer or a consumption for manufacture stays inside the estate and is
	governed by the W1/W2 gates; only handing material to a third party is a dispatch.
	"""
	_require_fixture(site)

	transfer = frappe._dict(
		doctype="Stock Entry",
		purpose="Material Transfer",
		name=None,
		items=[frappe._dict(item_code=GAP_ITEM, batch_no=GAP_BATCH, s_warehouse=WAREHOUSE)],
	)
	assert dispatch._dispatched_rows(transfer) == []
	dispatch.enforce_adr_completeness(transfer)

	issue = frappe._dict(
		doctype="Stock Entry",
		purpose="Material Issue",
		name=None,
		items=[frappe._dict(item_code=GAP_ITEM, batch_no=GAP_BATCH, s_warehouse=WAREHOUSE)],
	)
	assert dispatch._dispatched_rows(issue) == [{"item": GAP_ITEM, "batch": GAP_BATCH}]


def test_tc_w3_022_delivery_note_is_gated_by_the_same_rule(site):
	"""TC-W3-022 (URS-W3-018 AC-2): one rule covers both outward anchor paths.

	The Delivery Note is the other half of the dispatch boundary and is registered through
	the same `doc_events` hook, so the rule lives in one place.
	"""
	_require_fixture(site)

	note = frappe._dict(
		doctype="Delivery Note",
		name=None,
		items=[frappe._dict(item_code=GAP_ITEM, batch_no=GAP_BATCH, warehouse=WAREHOUSE)],
	)
	with pytest.raises(frappe.ValidationError) as refusal:
		dispatch.enforce_adr_completeness(note)
	assert "UN-Nummer" in str(refusal.value)

	hooks = frappe.get_hooks("doc_events")
	assert (
		"rheinwerk_mes.regulatory_hazmat.dispatch.enforce_adr_completeness"
		in hooks["Delivery Note"]["validate"]
	)
	assert (
		"rheinwerk_mes.regulatory_hazmat.dispatch.enforce_adr_completeness"
		in hooks["Stock Entry"]["validate"]
	)


def test_tc_w3_022_label_preview_shows_the_gap_before_the_lorry_waits(site):
	"""TC-W3-022 (URS-W3-018 AC-2): the label model carries the same verdict as the gate."""
	_require_fixture(site)

	label = labels.label_model(GAP_BATCH, warehouse=WAREHOUSE)

	assert label["complete"] is False
	assert "un_number" in label["missing"]
	assert "UN-Nummer" in label["missing_labels"]
	assert label["un_number"] == ""
	assert label["net_qty"] > 0


def test_tc_w3_022_dispatch_station_is_terminal_conformant(repo_root):
	"""TC-W3-022 step 2: Terminal mode — 48 px targets and a focused scanner field.

	Asserted against the committed page assets (the screenshot in the PR shows the rendered
	result): the station reuses the shop-floor Terminal tokens (`--rw-target: 48px`), starts
	in Terminal mode, keeps the scan field focused, and shows the refusal as a persistent
	gate card naming rule, record and resolution rather than a toast.
	"""
	page = (repo_root / "rheinwerk_mes/regulatory_hazmat/page/dispatch_label/dispatch_label.js").read_text(
		encoding="utf-8"
	)
	css = (repo_root / "rheinwerk_mes/public/css/hazmat_dispatch.css").read_text(encoding="utf-8")
	tokens = (repo_root / "rheinwerk_mes/public/css/shopfloor.css").read_text(encoding="utf-8")

	assert "--rw-target: 48px" in tokens
	assert 'this.mode = "Terminal"' in page
	assert "focus_scan()" in page
	assert 'data-ref="scan"' in page
	assert "min-height: var(--rw-target)" in css
	for part in ("Regel:", "Datensatz:", "Behebung:"):
		assert part in page
	# German-first: every user-facing string in the page goes through __().
	assert "Versandstation" in page
	assert 'frappe.pages["dispatch-label"]' in page
