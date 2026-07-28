"""Electronic Signature — the append-only record of one signed dispositive act.

Policy: `docs/decisions/DEC-W2-029-e-signature-policy.md` (URS-W2-029); enforcement design:
`docs/design/W3-esignature-enforcement.md`.

A signature is never edited and never deleted: a wrong signature is superseded by signing
again, which is why the controller refuses every write to a stored record except the two
consumption stamps the gate sets when it spends the signature on a transition.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

#: The only fields a stored signature may still gain — set once, by the consuming gate.
CONSUMPTION_FIELDS: tuple[str, ...] = ("consumed_by", "consumed_at")


class ElectronicSignature(Document):
	def validate(self) -> None:
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if before is None:
			return
		changed = [
			field.fieldname
			for field in self.meta.fields
			if field.fieldname not in CONSUMPTION_FIELDS
			and (self.get(field.fieldname) or None) != (before.get(field.fieldname) or None)
		]
		if changed:
			frappe.throw(
				_(
					"Elektronische Unterschrift {0} ist unveränderlich. Geänderte Felder: {1}. "
					"Eine falsche Unterschrift wird durch eine neue Unterschrift ersetzt."
				).format(self.name, ", ".join(sorted(changed))),
				title=_("Unterschrift unveränderlich"),
			)
		if before.get("consumed_by") and self.get("consumed_by") != before.get("consumed_by"):
			frappe.throw(
				_("Unterschrift {0} wurde bereits für {1} verwendet.").format(
					self.name, before.get("consumed_by")
				),
				title=_("Unterschrift verbraucht"),
			)

	def on_trash(self) -> None:
		frappe.throw(
			_("Elektronische Unterschriften dürfen nicht gelöscht werden ({0}).").format(self.name),
			title=_("Unterschrift unveränderlich"),
		)
