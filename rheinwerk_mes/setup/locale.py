"""German-first locale baseline (URS-W0-016).

The plant thinks in German, DD.MM.YYYY and kg, so the locale is estate
configuration owned by committed code — never a per-site manual setting. Applied
from `setup_w0()` on install and on every `bench migrate`, and re-asserted by the
fixture seeder so a demo site and a CI site converge on the same rendering.
"""

from __future__ import annotations

import frappe

LANGUAGE = "de"
COUNTRY = "Germany"
TIME_ZONE = "Europe/Berlin"
DATE_FORMAT = "dd.mm.yyyy"
TIME_FORMAT = "HH:mm:ss"
# German convention: thousands separator ".", decimal separator ",".
NUMBER_FORMAT = "#.###,##"
FIRST_DAY_OF_WEEK = "Monday"
MASS_UOM = "Kg"

SYSTEM_SETTINGS = {
	"language": LANGUAGE,
	"country": COUNTRY,
	"time_zone": TIME_ZONE,
	"date_format": DATE_FORMAT,
	"time_format": TIME_FORMAT,
	"number_format": NUMBER_FORMAT,
	"first_day_of_the_week": FIRST_DAY_OF_WEEK,
}


def install_locale() -> dict[str, str]:
	"""Pin the site to the German locale and kg as the default stock UoM."""
	settings = frappe.get_single("System Settings")
	settings.update(SYSTEM_SETTINGS)
	settings.save(ignore_permissions=True)
	if frappe.db.exists("UOM", MASS_UOM):
		frappe.db.set_single_value("Stock Settings", "stock_uom", MASS_UOM)
	frappe.clear_cache()
	return dict(SYSTEM_SETTINGS)
