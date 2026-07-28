"""FEFO picking-order contract — CHAR-FEFO-PICK-01.

URS-W0-012 (AC-3) · TC-W0-014 step 3.
Legacy baseline: `mes-plugins/mes-plugins-material-flow-resources/src/main/java/com/
qcadoo/mes/materialFlowResources/service/ResourceManagementServiceImpl.java:1015-1027`
with the algorithm enum in `.../constants/WarehouseAlgorithm.java:26-27`
(`SachetCognition/Chem_mes@master`).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..api import Resolution
from ..legacy_rules import picking_order
from ..registry import Contract, register


def _check_picking_order(resolution: Resolution, case: Mapping[str, Any]) -> None:
	picked = tuple(resolution.callable_(case["resources"], case["algorithm"]))
	expected = tuple(case["expected"]["picking_order"])
	assert picked == expected, (
		f"{case['id']}: {case['algorithm']} picking order drifted — expected {expected}, "
		f"got {picked} (implementation: {resolution.source})"
	)


PICKING_ORDER = register(
	Contract(
		id="CHAR-FEFO-PICK-01",
		title="FEFO picks the earliest expiry first (BATCH-A-0002 before BATCH-A-0001)",
		concern="picking_order",
		legacy_source="ResourceManagementServiceImpl.java:1015-1027; WarehouseAlgorithm.java:26-27",
		fixture="warehouse_picking.json",
		fallback=picking_order,
		checker=_check_picking_order,
		urs_ids=("URS-W0-012",),
		tc_ids=("TC-W0-014",),
	)
)
