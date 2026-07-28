// Hazmat chip on the anchor Item form (W2-7 · URS-W2-024 design conformance).
//
// The anchor DocType is never forked: this client extension only reads the Custom Fields
// this app owns (`rw_hazmat_profile`, `rw_hazmat_mandatory`) and renders the profile with the
// shared chip helper (`public/js/hazmat.js`) — icon + label + colour, never colour alone.
// Nothing hides behind progressive disclosure: UN number and Lagerklasse are in the chip.

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (!frm.doc.rw_hazmat_profile) {
			if (frm.doc.rw_hazmat_mandatory) {
				frm.dashboard.add_indicator(__("Gefahrstoffprofil fehlt"), "red");
			}
			return;
		}
		frappe.db.get_doc("Hazmat Profile", frm.doc.rw_hazmat_profile).then((profile) =>
			rheinwerk_mes.regulatory_hazmat.show_chip(frm, {
				profile: profile.name,
				storage_class: profile.storage_class,
				label: `${profile.un_number} · ${__("Lagerklasse {0}", [profile.storage_class])}`,
			})
		);
	},
});
