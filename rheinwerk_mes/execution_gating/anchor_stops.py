"""Anchor hard stops kept and verified, not re-implemented (W1-3 · URS-W1-010…URS-W1-013).

The substrate's own refusals are the implementation; W1-3 owns only their *declaration*
and their verification. This registry is the machine-readable form of that declaration:
one row per adopted hard stop with the ERPNext source that raises it, the transition or
posting it guards and its mapped test case. `tests/acceptance/test_w1_gating_anchor_stops.py`
drives the substrate through the `rheinwerk_mes` workflow and asserts each row still fires;
the W1-10 behaviour record (URS-W1-031) consumes the same rows for its Adopt half.

Nothing here may weaken a substrate rule: no anchor DocType is forked, no anchor validation
is bypassed and no `ignore_validate` flag is set on an anchor posting path. Where the estate
deliberately keeps the anchor rule over the donor's softer behaviour — expired stock — the
divergence is recorded (URS-W1-030, verdict Divergence in the W1-10 record).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnchorHardStop:
	"""One adopted substrate refusal that W1 keeps and verifies."""

	id: str
	urs: str
	tc: str
	guards: str
	anchor_source: str
	#: Developer-facing record of the refusal (W1-10 input, never rendered to a user).
	behaviour: str
	#: "Parity" — the target keeps the anchor rule as the donor would expect; "Divergence" —
	#: the estate deliberately keeps the (stricter) anchor rule over the donor behaviour.
	verdict: str
	note: str = ""


ANCHOR_HARD_STOPS: tuple[AnchorHardStop, ...] = (
	AnchorHardStop(
		id="ANCHOR-OVERPRODUCTION",
		urs="URS-W1-010",
		tc="TC-W1-011",
		guards="Manufacture / material-transfer posting above ordered qty + allowance",
		anchor_source="erpnext/stock/doctype/stock_entry/stock_entry.py:965-975 (allowed "
		"quantity against the order) and erpnext/manufacturing/doctype/work_order/services/"
		"status.py:208-224 (`StockOverProductionError`)",
		behaviour="Recording more output than plan + over-production allowance throws and "
		"writes no Stock Ledger Entry.",
		verdict="Parity",
	),
	AnchorHardStop(
		id="ANCHOR-STOPPED-FREEZE",
		urs="URS-W1-011",
		tc="TC-W1-012",
		guards="Job Card submission against a stopped Work Order",
		anchor_source="erpnext/manufacturing/doctype/job_card/job_card.py:1452-1467 "
		"(`validate_work_order` / `is_work_order_closed`, which covers Stopped) and :904-910 "
		"(`validate_job_card`, on submit)",
		behaviour="A stopped Work Order freezes execution: submitting a job card against it is refused.",
		verdict="Parity",
	),
	AnchorHardStop(
		id="ANCHOR-CLOSED-TERMINAL",
		urs="URS-W1-012",
		tc="TC-W1-013",
		guards="stop / re-open of a closed Work Order",
		anchor_source="erpnext/manufacturing/doctype/work_order/work_order.py "
		"(`stop_unstop`, work_order.py:1131-1132)",
		behaviour="A closed Work Order is terminal — it can neither be stopped nor re-opened; "
		"anchor Closed maps onto the terminal `exec_state`s.",
		verdict="Parity",
	),
	AnchorHardStop(
		id="ANCHOR-EXPIRED-BATCH",
		urs="URS-W1-013",
		tc="TC-W1-014",
		guards="outward posting / pick list against a batch past its expiry date",
		anchor_source="erpnext/stock/doctype/pick_list/pick_list.py:286-311 "
		"(`validate_expired_batches`, on save); "
		"erpnext/stock/doctype/stock_ledger_entry/stock_ledger_entry.py:287-299 "
		"(`validate_batch` — skipped for `voucher_type == 'Stock Entry'`, see note)",
		behaviour="Issuing or picking an expired batch is refused; the estate-wide policy is "
		"the anchor hard stop.",
		verdict="Divergence",
		note="Deliberate deviation from Plant A's FEFO-advisory behaviour (Qcadoo has no hard "
		"stop on issuing expired resources) — recorded in URS-W1-030, business sign-off "
		"required. Substrate gap: the anchor exempts stock consumption from its expiry throw "
		"(SLE `validate_batch` skips Stock Entry vouchers; "
		"stock/services/serial_batch_bundle_service.py:110-112 skips Material Issue/Transfer), "
		"so consumption is enforced by `rheinwerk_mes.execution_gating.expiry` as a hook; the "
		"pick-list half and the intake half stay purely anchor-adopted.",
	),
)


def by_id(stop_id: str) -> AnchorHardStop:
	"""Look up one adopted hard stop; raises `KeyError` when the id is unknown."""
	for stop in ANCHOR_HARD_STOPS:
		if stop.id == stop_id:
			return stop
	raise KeyError(stop_id)
