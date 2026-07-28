"""Plant B (OFBiz) master-data extractor — URS-W0-010.

Reads an OFBiz entity-engine XML export (`applications/product/entitydef/
product-entitymodel.xml` for `Product`/`GoodIdentification`/`Facility`,
`applications/accounting/entitydef/accounting-entitymodel.xml` for `FixedAsset`).

CDM-08 rule enforced here: **machine FixedAssets import as Workstations only.** Asset
accounting (purchase cost, accounting class) stays with the group ERP and is deliberately
not carried (`✕`); non-machine asset types (buildings, property) are skipped entirely, so
no asset-ledger record can ever be produced by this migration.

Transforms:

* `item_code` ≈ `GoodIdentification[SKU].idValue` falling back to `Product.productId`.
* `stock_uom` ≈ `Product.quantityUomId` through `UOM_MAP`; an unmappable UoM produces an
  **exceptions-report entry, never a default** (URS-W0-010 AC-2).
* `warehouse` ≈ `Facility` rows with `facilityTypeId="WAREHOUSE"`; plants/offices are not
  warehouses and are not carried.
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

#: OFBiz `Uom` identifiers → substrate UoM names.
UOM_MAP = {
	"WT_kg": "Kg",
	"WT_g": "Gram",
	"VLIQ_L": "Litre",
	"PCE": "Nos",
}

#: `FixedAssetType` values that denote an operational machine (CDM-08).
MACHINE_ASSET_TYPES = frozenset({"PRODUCTION_EQUIPMENT", "EQUIPMENT", "MACHINE"})

WAREHOUSE_FACILITY_TYPE = "WAREHOUSE"

ITEM_GROUP_BY_PRODUCT_TYPE = {
	"FINISHED_GOOD": "Products",
	"RAW_MATERIAL": "Raw Material",
}

DIRECT_FIELDS = {
	"item": ("item_name",),
	"work_centre": ("workstation_name",),
	"warehouse": ("warehouse_name",),
}


def extract(path: str | Path) -> CanonicalExtract:
	"""Extract Plant B master data from the OFBiz entity XML at `path`."""
	root = ElementTree.parse(Path(path)).getroot()  # noqa: S314 — committed fixture, no external input
	records: list[CanonicalRecord] = []
	exceptions: list[MigrationException] = []

	sku_by_product = {
		element.get("productId"): element.get("idValue")
		for element in root.findall("GoodIdentification")
		if element.get("goodIdentificationTypeId") == "SKU"
	}

	for product in root.findall("Product"):
		product_id = product.get("productId", "")
		item_code = sku_by_product.get(product_id) or product_id
		stock_uom = UOM_MAP.get(product.get("quantityUomId", ""))
		if stock_uom is None:
			exceptions.append(
				MigrationException(
					entity="item",
					source_identifier=product_id,
					reason="unmappable_uom",
					detail=(
						f"OFBiz quantityUomId {product.get('quantityUomId')!r} has no canonical "
						"UoM equivalent; record not imported"
					),
				)
			)
			continue
		records.append(
			CanonicalRecord(
				entity="item",
				key=item_code,
				fields={
					"item_code": item_code,
					"item_name": product.get("productName"),
					"stock_uom": stock_uom,
					"item_group": ITEM_GROUP_BY_PRODUCT_TYPE.get(
						product.get("productTypeId", ""), "Raw Material"
					),
					"description": product.get("description") or product.get("productName"),
				},
				source_entity="Product",
				source_identifier=product_id,
			)
		)

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

	for facility in root.findall("Facility"):
		if facility.get("facilityTypeId") != WAREHOUSE_FACILITY_TYPE:
			continue
		records.append(
			CanonicalRecord(
				entity="warehouse",
				key=facility.get("facilityName", ""),
				fields={"warehouse_name": facility.get("facilityName"), "disposal_method": None},
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
