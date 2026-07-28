"""Wave W1 execution-gating setup — one idempotent entry point (W1-2 / W1-3).

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from `patches.txt`
(existing sites) so a clean install and a migration converge on the same configuration.
Everything the gates rely on that is *not* code lives here, created by committed code and
never by hand on a site (programme rule 1):

* the estate's over-production allowance is pinned to 0 % on the anchor Manufacturing
  Settings — the substrate default the over-production hard stop is verified against
  (URS-W1-010 AC-1). An allowance already configured by the business is left untouched.
* the `Execution Gate Log` (URS-W1-033) is asserted to be append-only, so a site whose
  DocType was tampered with fails loudly rather than silently accepting edits.

No anchor DocType is forked and no anchor validation is relaxed: the W1-3 hard stops are
the substrate's own (`rheinwerk_mes.execution_gating.anchor_stops`).
"""

from __future__ import annotations

import frappe
from frappe import _

MANUFACTURING_SETTINGS = "Manufacturing Settings"
OVERPRODUCTION_FIELD = "overproduction_percentage_for_work_order"
LOG_DOCTYPE = "Execution Gate Log"


def pin_overproduction_allowance() -> float:
	"""Pin the over-production allowance to 0 % when the estate has not configured one."""
	settings = frappe.get_single(MANUFACTURING_SETTINGS)
	current = settings.get(OVERPRODUCTION_FIELD)
	if current in (None, ""):
		settings.db_set(OVERPRODUCTION_FIELD, 0, update_modified=False)
		return 0.0
	return float(current)


def assert_gate_log_is_append_only() -> None:
	"""Guard the URS-W1-033 immutability contract of the audit log."""
	if not frappe.db.exists("DocType", LOG_DOCTYPE):
		frappe.throw(_("DocType {0} ist nicht installiert.").format(LOG_DOCTYPE))
	meta = frappe.get_meta(LOG_DOCTYPE)
	if not meta.in_create:
		frappe.throw(
			_("{0} muss unveränderlich bleiben (in_create), Protokolleinträge sind Audit-Nachweise.").format(
				LOG_DOCTYPE
			)
		)


def setup_w1_gating() -> None:
	"""Apply the W1-2 / W1-3 gating configuration; safe to re-run."""
	assert_gate_log_is_append_only()
	pin_overproduction_allowance()


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w1_gating()
