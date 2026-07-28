// Hazmat chip on the anchor Batch form (W2-7 · URS-W2-024 design conformance).
//
// Reads the effective profile through the server API (`views.batch_hazmat`), so the batch
// override for repacked goods and the item profile resolve in exactly one place. Status is
// icon + label + colour; the chip names the Lagerklasse and the UN number as data, and the
// SDS reference is one click away — nothing hides behind progressive disclosure.

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
				rheinwerk_mes.regulatory_hazmat.show_chip(frm, model.chip);
				if (model.overridden) {
					frm.dashboard.add_indicator(__("Chargenspezifisches Profil"), "orange");
				}
				if (model.profile && model.profile.sds_reference) {
					frm.dashboard.add_indicator(
						__("SDB: {0}", [model.profile.sds_reference]),
						"gray"
					);
				}
				frm.add_custom_button(__("Chargen-Trace"), () =>
					frappe.set_route("trace-ribbon", frm.doc.name)
				);
			});
	},
});
