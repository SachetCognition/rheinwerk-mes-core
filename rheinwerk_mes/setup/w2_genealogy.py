"""W2-1/2/3 installer — canonical Batch, `qa_state` workflow, genealogy tables (URS-W2-005).

Everything the genealogy module needs on a site is created here, idempotently, from
committed code (programme rule 1): the canonical-Batch Custom Fields (identity, qa_state,
expiry facets, genealogy links, advisories, `legacy_refs`), the quarantine flag on the W1
`Storage Location`, the QC-exemption flag on the anchor `Item`, and the
*Batch Quality Disposition* workflow carrying `qa_state` with its role gating.

The anchor `Batch` DocType is never forked — TC-W2-008 asserts the schema diff.

Invoked from `rheinwerk_mes.install.after_install` (fresh site) and from `patches.txt`
(existing sites), so both converge on the same schema.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from rheinwerk_mes.genealogy.qa_state import (
	BLOCKED,
	INITIAL_STATE,
	QUARANTINED,
	RELEASED,
	STATE_LABELS,
	STATES,
	WORKFLOW_NAME,
)
from rheinwerk_mes.setup.custom_fields import LEGACY_REFS_FIELDNAME

GENEALOGY_MODULE = "Genealogy"
QUALITY_ROLE = "Quality Manager"

#: (from, to, action, role) — Qcadoo's reversible TRACKED ⇄ BLOCKED pair
#: (`BatchState.java:31-44`) plus the two Quarantined edges added by URS-W2-006.
TRANSITIONS: tuple[tuple[str, str, str, str], ...] = (
	(QUARANTINED, RELEASED, "Release Batch", QUALITY_ROLE),
	(QUARANTINED, BLOCKED, "Block Batch", QUALITY_ROLE),
	(RELEASED, BLOCKED, "Block Batch", QUALITY_ROLE),
	(BLOCKED, RELEASED, "Release Batch", QUALITY_ROLE),
)

STATE_STYLES: dict[str, str] = {
	QUARANTINED: "Warning",
	RELEASED: "Success",
	BLOCKED: "Danger",
}


def custom_field_definitions() -> dict[str, list[dict]]:
	"""Canonical-Batch extensions (CDM-01) plus the two flags W2-3 needs."""
	return {
		"Batch": [
			{
				"fieldname": "rw_canonical_section",
				"label": _("Kanonische Charge"),
				"fieldtype": "Section Break",
				"insert_after": "expiry_date",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "qa_state",
				"label": _("Qualitätszustand"),
				"fieldtype": "Select",
				"options": "\n".join(STATES),
				"default": INITIAL_STATE,
				"insert_after": "rw_canonical_section",
				"read_only": 1,
				"in_standard_filter": 1,
				"in_list_view": 1,
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "qa_state_reason",
				"label": _("Begründung des Verwendungsentscheids"),
				"fieldtype": "Small Text",
				"insert_after": "qa_state",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "qty_original",
				"label": _("Ursprungsmenge (kg)"),
				"fieldtype": "Float",
				"precision": "6",
				"insert_after": "qa_state_reason",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "supplier_batch_no",
				"label": _("Lieferantencharge"),
				"fieldtype": "Data",
				"insert_after": "qty_original",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "genealogy_incomplete",
				"label": _("Spur unvollständig"),
				"fieldtype": "Check",
				"default": "0",
				"insert_after": "supplier_batch_no",
				"in_standard_filter": 1,
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "trace_boundary_date",
				"label": _("Spurgrenze (Datum)"),
				"fieldtype": "Date",
				"insert_after": "genealogy_incomplete",
				"depends_on": "eval:doc.genealogy_incomplete",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "rw_genealogy_section",
				"label": _("Genealogie"),
				"fieldtype": "Section Break",
				"insert_after": "trace_boundary_date",
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "genealogy_links",
				"label": _("Genealogie-Verknüpfungen"),
				"fieldtype": "Table",
				"options": "Genealogy Link",
				"insert_after": "rw_genealogy_section",
				"read_only": 1,
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "blocked_ancestors",
				"label": _("Gesperrte Vorgänger"),
				"fieldtype": "Table",
				"options": "Blocked Ancestor Advisory",
				"insert_after": "genealogy_links",
				"read_only": 1,
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": "qa_state_history",
				"label": _("Verlauf der Verwendungsentscheide"),
				"fieldtype": "Table",
				"options": "Batch QA State History",
				"insert_after": "blocked_ancestors",
				"read_only": 1,
				"module": GENEALOGY_MODULE,
			},
			# URS-W2-007: the W0 `legacy_refs` child table is reused — there is exactly one
			# legacy-identifier store in the estate.
			{
				"fieldname": "rw_legacy_refs_section",
				"label": _("Herkunftssysteme"),
				"fieldtype": "Section Break",
				"insert_after": "qa_state_history",
				"collapsible": 1,
				"module": GENEALOGY_MODULE,
			},
			{
				"fieldname": LEGACY_REFS_FIELDNAME,
				"label": _("Legacy-Referenzen"),
				"fieldtype": "Table",
				"options": "Legacy Ref",
				"insert_after": "rw_legacy_refs_section",
				"module": GENEALOGY_MODULE,
			},
		],
		"Storage Location": [
			{
				"fieldname": "is_quarantine_location",
				"label": _("Quarantäneplatz"),
				"fieldtype": "Check",
				"default": "0",
				"insert_after": "is_group",
				"in_standard_filter": 1,
				"module": GENEALOGY_MODULE,
			},
		],
		"Item": [
			{
				"fieldname": "qc_exempt",
				"label": _("Von der Quarantäne ausgenommen"),
				"fieldtype": "Check",
				"default": "0",
				"description": _(
					"Chargen dieses Artikels werden bei Anlage direkt freigegeben (QC-Ausnahmeliste, URS-W2-006)."
				),
				"insert_after": "has_expiry_date",
				"module": GENEALOGY_MODULE,
			},
		],
	}


def install_custom_fields() -> None:
	create_custom_fields(custom_field_definitions(), ignore_validate=True)


def _ensure_workflow_states() -> None:
	for state in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state,
					"style": STATE_STYLES[state],
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Workflow State", state, "style", STATE_STYLES[state])


def _ensure_workflow_actions() -> None:
	for _from_state, _to_state, action, _role in TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def install_workflow() -> str:
	"""Create/refresh the `qa_state` workflow on the anchor Batch; safe to re-run."""
	_ensure_workflow_states()
	_ensure_workflow_actions()

	workflow = (
		frappe.get_doc("Workflow", WORKFLOW_NAME)
		if frappe.db.exists("Workflow", WORKFLOW_NAME)
		else frappe.new_doc("Workflow")
	)
	workflow.update(
		{
			"workflow_name": WORKFLOW_NAME,
			"document_type": "Batch",
			"workflow_state_field": "qa_state",
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": 0,
		}
	)
	workflow.set("states", [])
	for state in STATES:
		workflow.append(
			"states",
			{"state": state, "doc_status": 0, "allow_edit": QUALITY_ROLE, "update_field": None},
		)
	workflow.set("transitions", [])
	for from_state, to_state, action, role in TRANSITIONS:
		workflow.append(
			"transitions",
			{
				"state": from_state,
				"action": action,
				"next_state": to_state,
				"allowed": role,
				"allow_self_approval": 1,
			},
		)
	workflow.flags.ignore_permissions = True
	workflow.save()
	return workflow.name


def install_permissions() -> None:
	"""Give the quality inspector write access to the anchor Batch (URS-W2-006 AC-4).

	The substrate ships Batch write to Item Manager only; the disposition belongs to
	quality, so the role gate has a role that can actually reach the record. Added as a
	Custom DocPerm — the anchor DocType itself is untouched.
	"""
	from frappe.permissions import add_permission, update_permission_property

	add_permission("Batch", QUALITY_ROLE, 0)
	for ptype in ("read", "write", "report", "export"):
		update_permission_property("Batch", QUALITY_ROLE, 0, ptype, 1)


def backfill_qa_state() -> int:
	"""Existing batches enter the workflow at its entry state (URS-W2-006 AC-1)."""
	rows = frappe.get_all(
		"Batch", filters={"qa_state": ("in", ("", None))}, pluck="name", limit_page_length=0
	)
	for name in rows:
		frappe.db.set_value("Batch", name, "qa_state", INITIAL_STATE, update_modified=False)
	return len(rows)


def setup_w2_genealogy() -> dict[str, object]:
	"""Install every W2-1/2/3 site artefact; safe to re-run."""
	install_custom_fields()
	install_permissions()
	summary: dict[str, object] = {"workflow": install_workflow()}
	summary["backfilled_batches"] = backfill_qa_state()
	summary["states"] = {state: STATE_LABELS[state] for state in STATES}
	frappe.clear_cache()
	frappe.db.commit()
	return summary


def execute() -> None:
	"""`patches.txt` entry point."""
	setup_w2_genealogy()
