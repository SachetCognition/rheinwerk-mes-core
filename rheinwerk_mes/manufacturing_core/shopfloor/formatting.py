"""German-first rendering helpers for the W1 shop-floor screens (URS-W1-034).

The plant thinks in DD.MM.YYYY and kg (design skill § "Content and language"), so every
date and quantity that reaches an operator passes through here instead of being formatted
ad hoc at the call site.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from frappe import _
from frappe.utils import flt, get_datetime, getdate

DATE_FORMAT = "%d.%m.%Y"
DATETIME_FORMAT = "%d.%m.%Y %H:%M"
MASS_UOM = "kg"


def format_date_de(value: Any) -> str:
	"""Render a date as DD.MM.YYYY; empty string for a missing value."""
	if not value:
		return ""
	parsed: date = value if isinstance(value, date) and not isinstance(value, datetime) else getdate(value)
	return parsed.strftime(DATE_FORMAT)


def format_datetime_de(value: Any) -> str:
	"""Render a timestamp as DD.MM.YYYY HH:MM; empty string for a missing value."""
	if not value:
		return ""
	return get_datetime(value).strftime(DATETIME_FORMAT)


def format_kg(value: Any, precision: int = 3) -> str:
	"""Render a mass in kg with German decimal separator, e.g. `500,000 kg`."""
	rendered = f"{flt(value):.{precision}f}".replace(".", ",")
	return f"{rendered} {MASS_UOM}"


def format_minutes(value: Any) -> str:
	"""Render a duration in minutes, translated ("120 Min.")."""
	return _("{0} Min.").format(f"{flt(value):.0f}")
