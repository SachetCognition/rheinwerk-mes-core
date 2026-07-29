"""Item-level UoM conversions (URS-W0-004).

Behavioural reference (not ported): Qcadoo expresses per-product unit conversions
as `unitConversionItem` rows hanging off `basic/model/product.xml` (see the
dossier ch. 3.1 §B.3 evidence index). The anchor equivalent is the ERPNext
`UOM Conversion Detail` table on `Item`, so no new entity is introduced — only
the two invariants Qcadoo enforces and ERPNext leaves open:

1. a conversion factor of 0 (or negative) is never a valid conversion;
2. the stock UoM converts to itself with factor exactly 1.

Resolution runs in `Decimal` so pack→stock quantities are exact (20 sack ×
25 kg = 500 kg, no binary-float drift), both for direct callers and for the
anchor transactions that accept a pack UoM on their item rows.
"""

from __future__ import annotations

from decimal import Decimal

import frappe
from frappe import _


def validate_uom_conversions(doc, method: str | None = None) -> None:
	"""`Item.validate` hook: reject non-positive and inconsistent conversion factors."""
	seen: set[str] = set()
	for row in doc.get("uoms") or []:
		factor = Decimal(str(row.conversion_factor or 0))
		if factor <= 0:
			frappe.throw(
				_("Zeile {0}: Der Umrechnungsfaktor für {1} muss größer als 0 sein.").format(
					row.idx, row.uom
				),
				title=_("Ungültige Mengeneinheiten-Umrechnung"),
			)
		if row.uom == doc.stock_uom and factor != 1:
			frappe.throw(
				_("Zeile {0}: Der Umrechnungsfaktor der Lagereinheit {1} muss 1 sein.").format(
					row.idx, row.uom
				),
				title=_("Ungültige Mengeneinheiten-Umrechnung"),
			)
		if row.uom in seen:
			frappe.throw(
				_("Zeile {0}: Für die Mengeneinheit {1} existiert bereits eine Umrechnung.").format(
					row.idx, row.uom
				),
				title=_("Ungültige Mengeneinheiten-Umrechnung"),
			)
		seen.add(row.uom)


def conversion_factor(item_code: str, uom: str) -> Decimal:
	"""Item-level factor from `uom` to the item's stock UoM."""
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if not stock_uom:
		frappe.throw(_("Artikel {0} existiert nicht.").format(item_code))
	if uom == stock_uom:
		return Decimal(1)
	factor = frappe.db.get_value(
		"UOM Conversion Detail",
		{"parent": item_code, "parenttype": "Item", "uom": uom},
		"conversion_factor",
	)
	if not factor:
		frappe.throw(
			_("Für Artikel {0} ist keine Umrechnung von {1} nach {2} hinterlegt.").format(
				item_code, uom, stock_uom
			),
			title=_("Fehlende Mengeneinheiten-Umrechnung"),
		)
	return Decimal(str(factor))


def resolve_to_stock_uom(item_code: str, qty: float | str | Decimal, uom: str) -> Decimal:
	"""Convert `qty` in `uom` to the item's stock UoM exactly (URS-W0-004 AC-1)."""
	return Decimal(str(qty)) * conversion_factor(item_code, uom)


# Anchor item rows name the resolved stock quantity differently (`Stock Entry Detail`
# vs. `BOM Item`); whichever the row has is recomputed.
STOCK_QTY_FIELDS: tuple[str, ...] = ("transfer_qty", "stock_qty")


def resolve_transaction_quantities(doc, method: str | None = None) -> None:
	"""`validate` hook on anchor transactions: recompute every item row's conversion
	factor and stock quantity from the item-level conversion table.

	ERPNext falls back to the global `UOM Conversion Factor` table and resolves in
	binary floats; Qcadoo resolves against the product's own `unitConversionItem`
	rows only. Rewriting the row here keeps pack quantities deterministic and exact,
	and makes a pack UoM without an item-level conversion a hard error.
	"""
	for row in doc.get("items") or []:
		if not row.get("item_code") or not row.get("uom"):
			continue
		factor = conversion_factor(row.item_code, row.uom)
		if row.meta.has_field("conversion_factor"):
			row.conversion_factor = float(factor)
		resolved = Decimal(str(row.get("qty") or 0)) * factor
		for fieldname in STOCK_QTY_FIELDS:
			if row.meta.has_field(fieldname):
				row.set(fieldname, float(resolved))
