"""Plant B (OFBiz) master-data extractor — URS-W0-010.

Reads an OFBiz entity-engine XML export — the interchange format the entity engine writes
for the Derby-backed Plant B instance (`webtools` entity export) — and covers:

* `Product` + `GoodIdentification` → `item` (`product-entitymodel.xml`)
* `FixedAsset` machine groups → `work_centre` (`accounting-entitymodel.xml:630`)
* `Facility` of type `WAREHOUSE` → `warehouse` (`product-entitymodel.xml:996`)

CDM-08 (ADR-010) is enforced here: **machine FixedAssets import as Workstations only.**
Asset accounting — `purchaseCost`, `salvageValue`, `depreciation`, `classEnumId` — is
deliberately not carried; it stays with the group ERP. Non-machine asset types (property,
vehicles, hardware) are skipped entirely, so this migration can never produce an
asset-ledger record.

`Product.quantityUomId` is translated through `UOM_MAP`; an unmappable unit produces an
exceptions-report entry and no item, never a defaulted UoM (URS-W0-010 AC-2).
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from pathlib import Path

from rheinwerk_mes.integration.migration.canonical import (
	CanonicalExtract,
	CanonicalRecord,
	MigrationException,
)

DEFAULT_FIXTURE = "tests/fixtures/legacy/ofbiz/plant-b-entities.xml"

#: OFBiz `Uom` identifiers (`framework/common/data/UnitData.xml`) → substrate UoM names.
UOM_MAP = {
	"WT_kg": "Kg",
	"WT_g": "Gram",
	"VLIQ_L": "Litre",
	"OTH_ea": "Nos",
}

#: `FixedAssetType` values denoting an operational machine or machine group (CDM-08);
#: `GROUP_EQUIPMENT` is OFBiz's "group of machines, used for task and routing definition"
#: (`applications/datamodel/data/seed/AccountingSeedData.xml:138`).
MACHINE_ASSET_TYPES = frozenset({"PRODUCTION_EQUIPMENT", "GROUP_EQUIPMENT", "EQUIPMENT"})

WAREHOUSE_FACILITY_TYPE = "WAREHOUSE"

SKU_IDENTIFICATION_TYPE = "SKU"

ITEM_GROUP_BY_PRODUCT_TYPE = {
	"FINISHED_GOOD": "Products",
	"SUBASSEMBLY": "Sub Assemblies",
	"RAW_MATERIAL": "Raw Material",
}

DEFAULT_ITEM_GROUP = "Raw Material"

#: Fields this source maps with the CDM `=` (direct) legend.
DIRECT_FIELDS = {
	"item": ("item_code", "item_name", "description"),
	"work_centre": ("workstation_name",),
	"warehouse": ("warehouse_name",),
}


def extract(path: str | Path) -> CanonicalExtract:
	"""Extract Plant B master data from the OFBiz entity XML export at `path`."""
	root = ElementTree.parse(Path(path)).getroot()  # noqa: S314 — controlled export, no external input
	records: list[CanonicalRecord] = []
	exceptions: list[MigrationException] = []

	sku_by_product = {
		element.get("productId"): element.get("idValue")
		for element in root.iter("GoodIdentification")
		if element.get("goodIdentificationTypeId") == SKU_IDENTIFICATION_TYPE
	}

	for product in root.iter("Product"):
		product_id = product.get("productId", "")
		source_uom = product.get("quantityUomId", "")
		stock_uom = UOM_MAP.get(source_uom)
		if stock_uom is None:
			exceptions.append(
				MigrationException(
					entity="item",
					source_entity="Product",
					source_identifier=product_id,
					reason="unmappable_uom",
					detail=(
						f"quantityUomId {source_uom!r} hat keine kanonische Mengeneinheit; "
						"Artikel nicht importiert"
					),
				)
			)
			continue
		item_code = sku_by_product.get(product_id) or product_id
		records.append(
			CanonicalRecord(
				entity="item",
				key=item_code,
				fields={
					"item_code": item_code,
					"item_name": product.get("productName"),
					"stock_uom": stock_uom,
					"item_group": ITEM_GROUP_BY_PRODUCT_TYPE.get(
						product.get("productTypeId", ""), DEFAULT_ITEM_GROUP
					),
					"description": product.get("description") or product.get("productName"),
				},
				source_entity="Product",
				source_identifier=product_id,
			)
		)

	for asset in root.iter("FixedAsset"):
		if asset.get("fixedAssetTypeId") not in MACHINE_ASSET_TYPES:
			continue
		asset_id = asset.get("fixedAssetId", "")
		records.append(
			CanonicalRecord(
				entity="work_centre",
				key=asset.get("fixedAssetName") or asset_id,
				# Asset accounting (purchaseCost, classEnumId, depreciation) stays with the
				# group ERP (CDM-08/ADR-010); `productionCapacity` is a weight throughput and
				# has no anchor equivalent — capacity norms are modelled in W3.
				fields={"workstation_name": asset.get("fixedAssetName") or asset_id},
				source_entity="FixedAsset",
				source_identifier=asset_id,
			)
		)

	for facility in root.iter("Facility"):
		if facility.get("facilityTypeId") != WAREHOUSE_FACILITY_TYPE:
			continue
		records.append(
			CanonicalRecord(
				entity="warehouse",
				key=facility.get("facilityName") or facility.get("facilityId", ""),
				fields={"warehouse_name": facility.get("facilityName") or facility.get("facilityId")},
				source_entity="Facility",
				source_identifier=facility.get("facilityId", ""),
			)
		)

	return CanonicalExtract(
		source="ofbiz",
		records=tuple(records),
		exceptions=tuple(exceptions),
		direct_fields=DIRECT_FIELDS,
	)
