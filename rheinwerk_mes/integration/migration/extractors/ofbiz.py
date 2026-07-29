"""Plant B (OFBiz) work-centre extractor — URS-W0-005 / URS-W0-010 (CDM-08, ADR-010).

Reads an OFBiz entity-engine XML export (`FixedAsset` from
`applications/accounting/entitydef/accounting-entitymodel.xml`) and maps machine groups to
the canonical `work_centre` entity.

CDM-08 rule enforced here: **machine FixedAssets import as Workstations only.** Asset
accounting (`purchaseCost`, `accountingClassId`) stays with the group ERP and is
deliberately not carried; non-machine asset types (buildings, property) are skipped
entirely, so no asset-ledger record can ever be produced by this migration.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from pathlib import Path

from rheinwerk_mes.integration.migration.canonical import CanonicalExtract, CanonicalRecord

DEFAULT_FIXTURE = "tests/fixtures/legacy/ofbiz/plant-b-entities.xml"

#: `FixedAssetType` values that denote an operational machine (CDM-08).
MACHINE_ASSET_TYPES = frozenset({"PRODUCTION_EQUIPMENT", "EQUIPMENT", "MACHINE"})

DIRECT_FIELDS = {"work_centre": ("workstation_name",)}


def extract(path: str | Path) -> CanonicalExtract:
	"""Extract Plant B machine groups as canonical `work_centre` records."""
	root = ElementTree.parse(Path(path)).getroot()  # noqa: S314 — committed fixture, no external input
	records: list[CanonicalRecord] = []

	for asset in root.findall("FixedAsset"):
		if asset.get("fixedAssetTypeId") not in MACHINE_ASSET_TYPES:
			continue
		asset_id = asset.get("fixedAssetId", "")
		records.append(
			CanonicalRecord(
				entity="work_centre",
				key=asset_id,
				# `purchaseCost` / `accountingClassId` are deliberately dropped: asset
				# accounting stays with the group ERP (CDM-08, ADR-010).
				fields={"workstation_name": asset_id, "production_line": None, "division": None},
				source_entity="FixedAsset",
				source_identifier=asset_id,
			)
		)

	return CanonicalExtract(source="ofbiz", records=tuple(records), direct_fields=DIRECT_FIELDS)
