"""W1-5 per-warehouse disposal algorithms and the FEFO parity contract.

TC-W1-021 (URS-W1-020) — per-warehouse FIFO/LIFO/FEFO/LEFO disposal order on the anchor
    ledger (RM Lager Nord = FEFO, FG Lager Süd = FIFO).
CHAR-FEFO-PICK-01, parity leg of TC-W1-030 (URS-W1-020) — the frozen FEFO fixture now runs
    against the production entrypoint `rheinwerk_mes.warehouse.contracts.picking_order`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WAREHOUSE_ALGORITHM = "rheinwerk_mes.warehouse.disposal.warehouse_algorithm"
PICKING_ORDER_FOR_WAREHOUSE = "rheinwerk_mes.warehouse.disposal.picking_order_for_warehouse"
ALLOCATE = "rheinwerk_mes.warehouse.disposal.allocate"

RM = "RM Lager Nord - RWC"
FG = "FG Lager Süd - RWC"


def test_char_fefo_pick_01_runs_against_production_contract():
	"""CHAR-FEFO-PICK-01 (TC-W1-030 / URS-W1-020): the offline parity fixture resolves to
	the production `picking_order` and reproduces the Qcadoo warehouse-algorithm ordering
	(BATCH-A-0002, 30.06.2026, before BATCH-A-0001, 31.12.2026), with no site required."""
	sys.path.insert(0, str(REPO_ROOT / "tests"))
	from characterisation import api, legacy_rules

	resolution = api.resolve("picking_order", legacy_rules.picking_order)
	assert resolution.is_target_implementation
	assert resolution.entrypoint == "rheinwerk_mes.warehouse.contracts.picking_order"

	fixture = json.loads(
		(REPO_ROOT / "tests/characterisation/fixtures/warehouse_picking.json").read_text("utf-8")
	)
	for case in fixture["cases"]:
		result = resolution.callable_(case["resources"], case["algorithm"])
		assert list(result) == case["expected"]["picking_order"], case["id"]


def test_picking_order_covers_all_four_algorithms():
	"""TC-W1-021 (URS-W1-020): the production contract orders resources for every Qcadoo
	`WarehouseAlgorithm`, and an unknown algorithm falls back to FIFO
	(`WarehouseAlgorithm.parseString`)."""
	from rheinwerk_mes.warehouse.contracts import picking_order

	resources = [
		{
			"batch": "OLD-NEAR",
			"expiration_date": "30.06.2026",
			"available_quantity": 50,
			"time": "01.01.2026",
		},
		{
			"batch": "NEW-FAR",
			"expiration_date": "31.12.2026",
			"available_quantity": 500,
			"time": "01.05.2026",
		},
	]
	assert picking_order(resources, "FIFO") == ("OLD-NEAR", "NEW-FAR")
	assert picking_order(resources, "LIFO") == ("NEW-FAR", "OLD-NEAR")
	assert picking_order(resources, "FEFO") == ("OLD-NEAR", "NEW-FAR")
	assert picking_order(resources, "LEFO") == ("NEW-FAR", "OLD-NEAR")
	assert picking_order(resources, "unknown-code") == picking_order(resources, "FIFO")


def test_tc_w1_021_disposal_algorithm_is_per_warehouse(site):
	"""TC-W1-021 (URS-W1-020): the disposal strategy lives on the warehouse, so RM Lager
	Nord picks FEFO (earliest expiry BATCH-A-0002 first) while FG Lager Süd picks FIFO
	(earliest intake BATCH-C-1001 first) — unlike the anchor's single global setting."""
	warehouse_algorithm = site.get_attr(WAREHOUSE_ALGORITHM)
	picking_order_for_warehouse = site.get_attr(PICKING_ORDER_FOR_WAREHOUSE)
	allocate = site.get_attr(ALLOCATE)

	assert warehouse_algorithm(RM) == "FEFO"
	assert warehouse_algorithm(FG) == "FIFO"

	fefo = picking_order_for_warehouse("RW-CHM-0001", RM)
	assert fefo[0] == "BATCH-A-0002"
	assert set(fefo) == {"BATCH-A-0001", "BATCH-A-0002"}

	fifo = picking_order_for_warehouse("RW-CHM-0003", FG)
	assert fifo == ("BATCH-C-1001", "BATCH-C-1002")

	allocation = allocate("RW-CHM-0001", RM, 20)
	assert allocation[0][0] == "BATCH-A-0002"
	assert sum(qty for _, qty in allocation) == 20
