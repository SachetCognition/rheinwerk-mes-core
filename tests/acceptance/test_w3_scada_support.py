"""Shared helpers for the W3-5 SCADA acceptance suites (URS-W3-015 … URS-W3-017).

Not a test module in itself: it arranges the seeded LINE-1 fixtures the way the SCADA path
needs them — tag mappings present, PO-2026-0001 In Progress with its job cards spawned —
reusing the W1-7 shop-floor helpers rather than duplicating the arrangement.
"""

from __future__ import annotations

from typing import Any

from test_w1_shopfloor_support import FILL, FIRST_ORDER, MIX, running_order

MIX_WORK_CENTRE = "LINE-1/MIX-01"
FILL_WORK_CENTRE = "LINE-1/FILL-01"

TAG_MIX_PRODUCED = "ns=2;s=Line1.Mix01.ProducedKg"
TAG_MIX_START = "ns=2;s=Line1.Mix01.OperationStart"
TAG_MIX_STOP = "ns=2;s=Line1.Mix01.OperationStop"
TAG_FILL_PRODUCED = "ns=2;s=Line1.Fill01.ProducedKg"

__all__ = [
	"FILL",
	"FILL_WORK_CENTRE",
	"FIRST_ORDER",
	"MIX",
	"MIX_WORK_CENTRE",
	"TAG_FILL_PRODUCED",
	"TAG_MIX_PRODUCED",
	"TAG_MIX_START",
	"TAG_MIX_STOP",
	"ensure_tag_mappings",
	"park_work_centre",
	"running_order",
	"tag_event",
]


def ensure_tag_mappings(site: Any) -> list[str]:
	"""The seeded OPC-UA tag mappings; re-seeded inside the test transaction if absent."""
	import pytest

	if not site.db.exists("DocType", "OPC UA Tag Mapping"):
		pytest.skip("OPC UA Tag Mapping is not installed on this site")
	from rheinwerk_mes.fixtures.seed import seed_scada_tag_mappings

	return seed_scada_tag_mappings()


def park_work_centre(site: Any, work_centre: str) -> int:
	"""Leave `work_centre` without work in progress — the unmatched-event precondition.

	The seeded routing puts MIX and FILL of the same order on LINE-1, so the TC-W3-018
	step-2 situation (a work centre where nothing runs) is arranged by removing the open
	job cards of that work centre; the test transaction is rolled back afterwards.
	"""
	names = site.get_all("Job Card", filters={"workstation": work_centre, "docstatus": 0}, pluck="name")
	for name in names:
		site.delete_doc("Job Card", name, force=True, ignore_permissions=True, delete_permanently=True)
	return len(names)


def tag_event(tag_address: str, value: float, equipment_timestamp: str, sequence: int = 0) -> Any:
	"""One published tag event — the shape the transport hands to the adapter."""
	from rheinwerk_mes.integration.scada.contracts import TagEvent

	return TagEvent(
		tag_address=tag_address,
		value=value,
		equipment_timestamp=equipment_timestamp,
		sequence=sequence,
	)


def test_support_module_exposes_helpers():
	"""Guard so the W3-5 suites keep their documented arrangement helpers."""
	assert callable(ensure_tag_mappings) and callable(park_work_centre) and callable(tag_event)
