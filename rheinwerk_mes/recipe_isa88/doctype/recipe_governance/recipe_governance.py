"""`Recipe Governance` — the governed BOM/Routing pair (CDM-04, ADR-006).

Requirements: URS-W1-014 … URS-W1-017. Every rule is enforced in this controller, so a
Desk workflow action, an API call (`governance.transition`) and a data import all behave
identically. The anchor `BOM` and `Routing` are never forked — this DocType references
them and the only anchor-side artefacts are Custom Fields and a `doc_event`
(`rheinwerk_mes/setup/w1_recipe_gov.py`, `hooks.py`).

Legacy baseline (semantics only): `SachetCognition/Chem_mes@master` ·
`technologies/states/constants/TechnologyState.java:33-66`,
`technologies/states/listener/TechnologyValidationService.java:91-707`,
`technologies/states/aop/listener/TechnologyValidationAspect.java:72-141`.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from rheinwerk_mes.recipe_isa88 import governance
from rheinwerk_mes.recipe_isa88.validators import Finding, ValidationReport

REASON_REQUIRED_TARGETS = (governance.DECLINED, governance.OUTDATED, governance.DRAFT)


class RecipeGovernance(Document):
	# ------------------------------------------------------------------ lifecycle hooks

	def validate(self) -> None:
		self._sync_routing()
		self._refresh_in_use_lock()
		previous = self._previous_state()

		if previous is None:
			self._validate_initial_state()
			return

		if self.gov_state == previous:
			self._guard_accepted_immutability(previous)
			return

		self._enforce_transition(previous, self.gov_state)

	def on_update(self) -> None:
		if self.gov_state == governance.ACCEPTED:
			self._outdate_predecessors()
		self._publish_state_to_bom()

	def on_trash(self) -> None:
		if self.gov_state in (governance.ACCEPTED, governance.OUTDATED):
			frappe.throw(
				_("Freigegebene und außer Kraft gesetzte Rezepte dürfen nicht gelöscht werden: {0}").format(
					self.name
				),
				title=_("Löschen gesperrt"),
			)
		frappe.db.set_value("BOM", self.bom, "rw_gov_state", "", update_modified=False)

	# --------------------------------------------------------------------- state helpers

	def _previous_state(self) -> str | None:
		"""`gov_state` as currently stored, or None for a new record."""
		if self.is_new():
			return None
		return frappe.db.get_value(self.doctype, self.name, "gov_state")

	def _sync_routing(self) -> None:
		if not self.routing:
			self.routing = frappe.db.get_value("BOM", self.bom, "routing")

	def _refresh_in_use_lock(self) -> None:
		orders = governance.active_orders_for_recipe(self.bom)
		self.in_use_lock = 1 if orders else 0
		self.in_use_orders = ", ".join(orders)

	def _validate_initial_state(self) -> None:
		"""URS-W1-014 AC-1: a new governance record starts in Draft."""
		if not self.gov_state:
			self.gov_state = governance.DRAFT
		if self.gov_state != governance.DRAFT:
			frappe.throw(
				_("Ein neuer Freigabedatensatz beginnt im Status {0}, nicht {1}.").format(
					_(governance.DRAFT), _(self.gov_state)
				),
				title=_("Ungültiger Startstatus"),
			)
		self._append_history(None, governance.DRAFT, self.transition_reason)
		self.transition_reason = None

	def _guard_accepted_immutability(self, state: str) -> None:
		"""URS-W1-016 AC-1: an Accepted record's governed references cannot change."""
		if state not in (governance.ACCEPTED, governance.OUTDATED):
			return
		before = self.get_doc_before_save()
		if before is None:
			return
		if (self.bom, self.routing) != (before.bom, before.routing):
			frappe.throw(
				_(
					"Rezept {0} ist im Status {1} und damit unveränderlich. Änderungen erfordern "
					"eine neue Stücklistenversion mit eigenem Freigabedatensatz."
				).format(self.name, _(state)),
				title=_("Rezeptänderung gesperrt"),
			)

	# ---------------------------------------------------------------------- transitions

	def _enforce_transition(self, previous: str, target: str) -> None:
		self._check_legality(previous, target)
		self._check_role(previous, target)
		self._check_reason(previous, target)

		if target in governance.VALIDATED_TARGETS:
			self._run_validators(target)
		if target in governance.LOCKED_TARGETS:
			self._check_in_use_lock(target)
		if target == governance.ACCEPTED:
			self._check_predecessors_unlocked()

		self._append_history(previous, target, self.transition_reason)
		self.transition_reason = None

	def _check_legality(self, previous: str, target: str) -> None:
		"""URS-W1-014 AC-3 — `TechnologyState.java:33-66` transition set."""
		if target not in governance.STATES:
			frappe.throw(
				_("{0} ist kein gültiger Freigabestatus.").format(target),
				title=_("Ungültiger Freigabestatus"),
			)
		if governance.can_change(previous, target):
			return
		allowed = governance.TRANSITIONS.get(previous, ())
		message = _("Statuswechsel {0} → {1} ist nicht zulässig.").format(_(previous), _(target))
		if allowed:
			message += " " + _("Zulässig ab {0}: {1}.").format(
				_(previous), ", ".join(_(state) for state in allowed)
			)
		else:
			message += " " + _("{0} ist ein Endstatus.").format(_(previous))
		frappe.throw(message, title=_("Statuswechsel abgelehnt"))

	def _check_role(self, previous: str, target: str) -> None:
		"""URS-W1-029: `gov_state` transitions are gated per transition, not per DocType."""
		roles = set(frappe.get_roles())
		if roles.intersection(governance.TRANSITION_ROLES):
			return
		frappe.throw(
			_("Statuswechsel {0} → {1} ist der Rolle {2} vorbehalten.").format(
				_(previous), _(target), _(governance.TECHNOLOGIST)
			),
			title=_("Keine Berechtigung"),
			exc=frappe.PermissionError,
		)

	def _check_reason(self, previous: str, target: str) -> None:
		if target in REASON_REQUIRED_TARGETS and not (self.transition_reason or "").strip():
			frappe.throw(
				_("Für den Statuswechsel {0} → {1} ist eine Begründung erforderlich.").format(
					_(previous), _(target)
				),
				title=_("Begründung fehlt"),
			)

	def _run_validators(self, target: str) -> None:
		"""URS-W1-015: the structural battery decides Checked/Accepted."""
		report = governance.evaluate_recipe(self.bom, self.routing)
		blocking = tuple(f for f in report.findings if f.validator != "not_used_in_active_order")
		self._store_validator_results(report, blocking)
		if not blocking:
			return
		# The refused transition aborts this save, so the evidence of *why* it was refused is
		# written straight to the stored record before raising (URS-W1-015 AC-3).
		self._persist_validator_results()
		frappe.throw(
			_("Freigabe von Rezept {0} abgelehnt. Fehlgeschlagene Strukturprüfungen:").format(self.bom)
			+ "\n"
			+ governance.describe_findings(blocking),
			title=_("Strukturprüfung fehlgeschlagen"),
		)

	def _store_validator_results(self, report: ValidationReport, blocking: tuple[Finding, ...]) -> None:
		"""URS-W1-015 AC-3: validator results are stored on the governance record."""
		failed = {finding.validator: finding for finding in blocking}
		self.set("validator_results", [])
		for validator in report.validators_run:
			finding = failed.get(validator)
			self.append(
				"validator_results",
				{
					"validator": validator,
					"validator_label": _(governance.VALIDATOR_LABELS.get(validator, validator)),
					"passed": 0 if finding else 1,
					"subject": finding.subject if finding else "",
					"message_key": finding.message_key if finding else "",
				},
			)
		self.validated_by = frappe.session.user
		self.validated_on = now()

	def _persist_validator_results(self) -> None:
		"""Write the in-memory validator rows to the stored record.

		Used on the refusal path only: `frappe.throw` unwinds the save, so the child rows
		built during `validate` would otherwise be lost with it.
		"""
		frappe.db.delete("Recipe Validator Result", {"parent": self.name, "parentfield": "validator_results"})
		for row in self.validator_results:
			row.name = frappe.generate_hash(length=10)
			row.parent = self.name
			row.parenttype = self.doctype
			row.parentfield = "validator_results"
			row.db_insert()
		frappe.db.set_value(
			self.doctype,
			self.name,
			{"validated_by": self.validated_by, "validated_on": self.validated_on},
			update_modified=False,
		)

	def _check_in_use_lock(self, target: str) -> None:
		"""URS-W1-017: an active order locks the recipe against Outdated/Declined."""
		orders = governance.active_orders_for_recipe(self.bom)
		if not orders:
			return
		frappe.throw(
			_(
				"Rezept {0} kann nicht auf {1} gesetzt werden: es wird von aktiven "
				"Fertigungsaufträgen verwendet ({2})."
			).format(self.bom, _(target), ", ".join(orders)),
			title=_("Verwendungssperre"),
		)

	def _check_predecessors_unlocked(self) -> None:
		"""URS-W1-016 AC-2 + URS-W1-017: accepting a successor outdates the predecessor, so
		a predecessor locked by an active order blocks the successor's acceptance."""
		for predecessor in self._predecessors():
			orders = governance.active_orders_for_recipe(predecessor)
			if orders:
				frappe.throw(
					_(
						"Rezept {0} kann nicht freigegeben werden: die Vorgängerversion {1} wird "
						"von aktiven Fertigungsaufträgen verwendet ({2})."
					).format(self.bom, predecessor, ", ".join(orders)),
					title=_("Verwendungssperre"),
				)

	def _predecessors(self) -> list[str]:
		"""Accepted governance records for the same item covering another BOM version."""
		return frappe.get_all(
			self.doctype,
			filters={
				"item": self.item,
				"gov_state": governance.ACCEPTED,
				"name": ("!=", self.name),
			},
			pluck="name",
			order_by="name",
		)

	def _outdate_predecessors(self) -> None:
		"""URS-W1-016 AC-2: accepting the successor moves the predecessor to Outdated."""
		for predecessor in self._predecessors():
			doc = frappe.get_doc(self.doctype, predecessor)
			doc.transition_reason = _("Ersetzt durch Rezeptversion {0}.").format(self.bom)
			doc.gov_state = governance.OUTDATED
			doc.save()

	# ------------------------------------------------------------------------ side data

	def _append_history(self, previous: str | None, target: str, reason: str | None) -> None:
		self.append(
			"state_history",
			{
				"from_state": previous or "",
				"to_state": target,
				"changed_by": frappe.session.user,
				"changed_at": now(),
				"reason": (reason or "").strip(),
			},
		)

	def _publish_state_to_bom(self) -> None:
		"""Mirror `gov_state` onto the anchor BOM's read-only pill field.

		Written with `db.set_value` because the BOM is submitted and must not be revalidated
		— the anchor stays untouched apart from the Custom Field this app owns.
		"""
		if not frappe.get_meta("BOM").get_field("rw_gov_state"):
			return
		frappe.db.set_value("BOM", self.bom, "rw_gov_state", self.gov_state, update_modified=False)
