// Hazmat chip on the anchor Batch form (W2-7 · URS-W2-024 design conformance).
//
// Reads the effective profile through the server API (`views.batch_hazmat`), so the batch
// override for repacked goods and the item profile resolve in exactly one place. Status is
// icon + label + colour; the chip names Lagerklasse, UN number and the SDS reference as data
// on one line — nothing hides behind progressive disclosure.

frappe.ui.form.on("Batch", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frappe
			.call("rheinwerk_mes.regulatory_hazmat.views.batch_hazmat", { batch: frm.doc.name })
			.then((response) => {
				const model = response.message;
				if (!model || !model.chip) {
					return;
				}
				const profile = model.profile || {};
				rheinwerk_mes.regulatory_hazmat.show_chip(frm, model.chip, [
					profile.sds_reference ? __("SDB {0}", [profile.sds_reference]) : "",
					profile.sds_revision_date ? __("Stand {0}", [profile.sds_revision_date]) : "",
					model.overridden ? __("Chargenspezifisches Profil (umgepackt)") : "",
				]);
				frm.add_custom_button(__("Chargen-Trace"), () =>
					frappe.set_route("trace-ribbon", frm.doc.name)
				);
			});
	},
});
