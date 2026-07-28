"""Item-level UoM conversions (URS-W0-004).

Behavioural reference (not ported): Qcadoo expresses per-product unit conversions
as `unitConversionItem` rows hanging off `basic/model/product.xml` (see the
dossier ch. 3.1 §B.3 evidence index). The anchor equivalent is the ERPNext
`UOM Conversion Detail` table on `Item`, so no new entity is introduced — only
the two invariants Qcadoo enforces and ERPNext leaves open:

1. a conversion factor of 0 (or negative) is never a valid conversion;
2. the stock UoM converts to itself with factor exactly 1.

Resolution runs in `Decimal` so pack→stock quantities are exact (20 sack ×
25 kg = 500 kg, no binary-float drift).
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
