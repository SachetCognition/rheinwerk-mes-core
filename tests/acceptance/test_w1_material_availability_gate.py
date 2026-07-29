"""URS-W1-008 · TC-W1-009 — material-availability hard gate at order start.

The gate is exercised over the anchor document shape (`Work Order` with `required_items`)
with the ledger and reservation reads faked, so the arithmetic, the per-component shortfall
list and the hard-gate wording are verified without a seeded site. The end-to-end journey
through the state machine (URS-W1-001) and real reservations (URS-W1-023) is TC-W1-009's
integration run, which lands with those requirements.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

frappe = pytest.importorskip("frappe")
gates = pytest.importorskip("rheinwerk_mes.execution_gating.gates")
availability = pytest.importorskip("rheinwerk_mes.warehouse.availability")

ORDER = "PO-2026-0001"
COMPONENT_A = "RW-CHM-0001"
COMPONENT_B = "RW-CHM-0002"
RM_WAREHOUSE = "RM Lager Nord - RWC"
WIP_WAREHOUSE = "WIP Fertigung - RWC"


class Context:
	"""Stand-in for the state machine's transition context (URS-W1-001)."""

	def __init__(self, doc, to_state: str, from_state: str = "Accepted") -> None:
		self.doc = doc
		self.to_state = to_state
		self.from_state = from_state
		self.refusals: list[str] = []

	def refuse(self, message: str) -> None:
		self.refusals.append(message)


def work_order(*components: dict[str, object]) -> frappe._dict:
	"""Anchor Work Order shape the gate reads: components in the recipe's order."""
	return frappe._dict(
		doctype="Work Order",
		name=ORDER,
		wip_warehouse=WIP_WAREHOUSE,
		source_warehouse=RM_WAREHOUSE,
		required_items=[
			frappe._dict({"source_warehouse": RM_WAREHOUSE, **component}) for component in components
		],
	)


@pytest.fixture
def stock(monkeypatch):
	"""Fake ledger balances and available quantities keyed by (item, warehouse)."""
	balances: dict[tuple[str, str], Decimal] = {}
	available: dict[tuple[str, str], Decimal] = {}

	def ledger_balance(item: str, warehouse: str) -> Decimal:
		return balances.get((item, warehouse), Decimal("0"))

	def available_qty(item: str, warehouse: str, exclude_voucher=None) -> Decimal:
		return available.get((item, warehouse), ledger_balance(item, warehouse))

	monkeypatch.setattr(gates, "ledger_balance", ledger_balance)
	monkeypatch.setattr(gates, "available_qty", available_qty)
	return frappe._dict(balances=balances, available=available)


@pytest.fixture
def logged(monkeypatch):
	"""Capture what the gate logs when it refuses (design conformance: refusals are logged)."""
	logger = MagicMock()
	monkeypatch.setattr(gates.frappe, "logger", lambda *args, **kwargs: logger)
	monkeypatch.setattr(gates.frappe, "session", frappe._dict(user="planner@rheinwerk.example"))
	return logger.info


# --------------------------------------------------------------------------------------
# AC-1 — the start is refused with a per-component shortfall list
# --------------------------------------------------------------------------------------


def test_start_refused_with_component_shortfall(stock, logged):
	"""AC-1 — 500 kg required against 400 kg available refuses, naming a 100 kg shortfall."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("400")
	context = Context(work_order({"item_code": COMPONENT_A, "required_qty": 500}), gates.IN_PROGRESS)

	gates.material_availability_gate(context)

	assert len(context.refusals) == 1
	message = context.refusals[0]
	assert "Regel:" in message and "Datensatz:" in message and "Behebung:" in message
	assert ORDER in message
	assert COMPONENT_A in message
	assert "Fehlmenge 100 kg" in message
	assert "verfügbar 400 kg" in message


def test_refusal_lists_every_short_component(stock, logged):
	"""AC-1 — each short component is listed with its own shortfall; sufficient ones are not."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("400")
	stock.balances[(COMPONENT_B, RM_WAREHOUSE)] = Decimal("60")
	doc = work_order(
		{"item_code": COMPONENT_A, "required_qty": 500},
		{"item_code": COMPONENT_B, "required_qty": 100},
	)

	shortfalls = gates.component_shortfalls(doc)

	assert [row["item"] for row in shortfalls] == [COMPONENT_A, COMPONENT_B]
	assert [row["shortfall"] for row in shortfalls] == [Decimal("100"), Decimal("40")]


def test_already_transferred_quantity_is_not_required_again(stock, logged):
	"""Only the outstanding requirement is gated — 200 kg already in WIP is not demanded twice."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("300")
	doc = work_order({"item_code": COMPONENT_A, "required_qty": 500, "transferred_qty": 200})

	assert gates.component_shortfalls(doc) == []


def test_gate_refusal_is_logged(stock, logged):
	"""Design conformance — a refusal is logged with gate, record and rule."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("400")
	context = Context(work_order({"item_code": COMPONENT_A, "required_qty": 500}), gates.IN_PROGRESS)

	gates.material_availability_gate(context)

	logged.assert_called_once()
	entry = logged.call_args.args[0]
	assert entry["gate"] == "material_availability_gate"
	assert entry["urs"] == "URS-W1-008"
	assert entry["reference_name"] == ORDER
	assert entry["to_state"] == gates.IN_PROGRESS
	assert "<b>" not in entry["detail"], "the logged detail carries no markup"


# --------------------------------------------------------------------------------------
# AC-2 — an available component lets the order start
# --------------------------------------------------------------------------------------


def test_start_allowed_when_every_component_is_available(stock, logged):
	"""AC-2 — 500 kg on hand in the source warehouse starts the order without refusal."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("500")
	context = Context(work_order({"item_code": COMPONENT_A, "required_qty": 500}), gates.IN_PROGRESS)

	gates.material_availability_gate(context)

	assert context.refusals == []
	logged.assert_not_called()


def test_gate_only_judges_the_start_transition(stock, logged):
	"""The gate hangs off * → In Progress; other transitions are none of its business."""
	stock.balances[(COMPONENT_A, RM_WAREHOUSE)] = Decimal("0")
	context = Context(work_order({"item_code": COMPONENT_A, "required_qty": 500}), "Completed")

	gates.material_availability_gate(context)

	assert context.refusals == []


def test_components_fall_back_to_the_order_warehouses(stock, logged):
	"""A component without its own source warehouse is drawn from the order's WIP warehouse."""
	stock.balances[(COMPONENT_A, WIP_WAREHOUSE)] = Decimal("500")
	doc = work_order({"item_code": COMPONENT_A, "required_qty": 500, "source_warehouse": None})

	assert gates.component_shortfalls(doc) == []
	assert gates.component_warehouse(doc.required_items[0], doc) == WIP_WAREHOUSE


# --------------------------------------------------------------------------------------
# AC-3 — reserved quantities are excluded from availability
# --------------------------------------------------------------------------------------


def _reservations(monkeypatch, rows: list[dict[str, object]]) -> None:
	monkeypatch.setattr(
		availability.frappe,
		"get_all",
		lambda doctype, filters=None, fields=None: [frappe._dict(row) for row in rows],
	)


def test_reserved_quantity_is_excluded_from_availability(monkeypatch):
	"""AC-3 — another order's draft reservation shrinks available, not on-hand."""
	monkeypatch.setattr(availability, "ledger_balance", lambda item, warehouse: Decimal("500"))
	_reservations(
		monkeypatch,
		[{"reserved_qty": 200, "delivered_qty": 0, "voucher_type": "Stock Entry", "voucher_no": "STE-1"}],
	)

	assert availability.available_qty(COMPONENT_A, RM_WAREHOUSE) == Decimal("300")


def test_delivered_reservations_no_longer_hold_stock(monkeypatch):
	"""A partly delivered reservation only holds back its outstanding quantity."""
	_reservations(
		monkeypatch,
		[{"reserved_qty": 200, "delivered_qty": 150, "voucher_type": "Stock Entry", "voucher_no": "STE-1"}],
	)

	assert availability.reserved_qty(COMPONENT_A, RM_WAREHOUSE) == Decimal("50")


def test_orders_own_reservation_does_not_block_its_start(monkeypatch):
	"""AC-3 — an order competes with other vouchers' reservations, never with its own."""
	_reservations(
		monkeypatch,
		[
			{"reserved_qty": 500, "delivered_qty": 0, "voucher_type": "Work Order", "voucher_no": ORDER},
			{
				"reserved_qty": 100,
				"delivered_qty": 0,
				"voucher_type": "Work Order",
				"voucher_no": "PO-2026-0002",
			},
		],
	)

	assert availability.reserved_qty(
		COMPONENT_A, RM_WAREHOUSE, exclude_voucher=("Work Order", ORDER)
	) == Decimal("100")


def test_gate_excludes_the_orders_own_reservation(monkeypatch):
	"""The gate passes its own voucher to the availability read, so AC-3 holds end to end."""
	seen: list[tuple[str, str] | None] = []

	def available_qty(item: str, warehouse: str, exclude_voucher=None) -> Decimal:
		seen.append(exclude_voucher)
		return Decimal("500")

	monkeypatch.setattr(gates, "available_qty", available_qty)
	monkeypatch.setattr(gates, "ledger_balance", lambda item, warehouse: Decimal("500"))

	gates.component_shortfalls(work_order({"item_code": COMPONENT_A, "required_qty": 500}))

	assert seen == [("Work Order", ORDER)]


# --------------------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------------------


def test_gate_is_registered_on_the_state_machine_hook():
	"""The gate reaches the state machine through the documented hook, not by editing it."""
	from rheinwerk_mes import hooks

	assert (
		"rheinwerk_mes.execution_gating.gates.material_availability_gate" in hooks.rheinwerk_exec_state_gates
	)
