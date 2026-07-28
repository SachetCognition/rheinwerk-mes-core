"""TC-W1-004 / TC-W1-005 — anchor reconciliation and the "status" vocabulary rule.

Verifies **URS-W1-004** (accept requires anchor submit; completion requires produced ≥
ordered or an explicit shortfall reason; the unqualified word "status" never appears as
a `rheinwerk_mes` field or label) through **TC-W1-004** and **TC-W1-005** of
`docs/test/TST-W1-production-core.md`.
"""

from __future__ import annotations

import re

import pytest
from test_w1_exec_state_support import (
	draft_order,
	force_state,
	submitted_order,
)

# Site-backed suite: skip (never fail) when the Frappe substrate is absent.
frappe = pytest.importorskip("frappe")
exec_state = pytest.importorskip("rheinwerk_mes.manufacturing_core.exec_state")


RHEINWERK_MODULES = (
	"Manufacturing Core",
	"Execution Gating",
	"Genealogy",
	"Quality",
	"Warehouse",
	"Recipe ISA88",
	"Regulatory Hazmat",
	"Integration",
)

#: The unqualified word only — `exec_state`, `qa_state`, `gov_state` and German
#: compounds such as "Statusverlauf" are the sanctioned vocabulary (ADR-004).
UNQUALIFIED_STATUS = re.compile(r"(?<![\w-])status(?![\w-])", re.IGNORECASE)


def test_acceptance_requires_the_anchor_to_be_submitted(site):
	"""URS-W1-004 AC-1 / TC-W1-004 step 1 — a draft Work Order cannot be accepted."""
	order = draft_order(site)
	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order.name, exec_state.ACCEPTED)
	assert order.name in str(excinfo.value)

	order = submitted_order(site)
	exec_state.transition(order.name, exec_state.ACCEPTED)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.ACCEPTED


def test_completion_below_ordered_quantity_requires_a_shortfall_reason(site):
	"""URS-W1-004 AC-2 / TC-W1-004 steps 2-3 — 480 kg of 500 kg needs a reason."""
	order = submitted_order(site)
	force_state(site, order, exec_state.IN_PROGRESS)
	site.db.set_value("Work Order", order.name, "produced_qty", 480, update_modified=False)

	with pytest.raises(frappe.ValidationError) as excinfo:
		exec_state.transition(order.name, exec_state.COMPLETED)
	assert "Mindermengen-Begründung" in str(excinfo.value)

	exec_state.transition(order.name, exec_state.COMPLETED, reason="Ausschuss Mischvorgang")
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.COMPLETED
	assert exec_state.state_history(order.name)[-1]["reason"] == "Ausschuss Mischvorgang"


def test_completion_at_full_quantity_needs_no_reason(site):
	"""URS-W1-004 AC-2 / TC-W1-004 — produced ≥ ordered completes without a reason."""
	order = submitted_order(site)
	force_state(site, order, exec_state.IN_PROGRESS)
	site.db.set_value("Work Order", order.name, "produced_qty", order.qty, update_modified=False)
	exec_state.transition(order.name, exec_state.COMPLETED)
	assert site.db.get_value("Work Order", order.name, "exec_state") == exec_state.COMPLETED


def test_no_unqualified_status_in_installed_custom_fields(site):
	"""URS-W1-004 AC-3 / TC-W1-005 — the installed catalogue is clean too."""
	rows = site.get_all(
		"Custom Field",
		filters={"module": ("in", RHEINWERK_MODULES)},
		fields=["dt", "fieldname", "label"],
	)
	offenders = [
		f"{row.dt}.{row.fieldname} ({row.label})"
		for row in rows
		if UNQUALIFIED_STATUS.search(row.fieldname or "") or UNQUALIFIED_STATUS.search(row.label or "")
	]
	assert not offenders, f"unqualified 'status' on installed custom fields: {offenders}"
