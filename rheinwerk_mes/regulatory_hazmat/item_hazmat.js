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
				// The gate that will refuse batch creation, named before it fires.
				rheinwerk_mes.regulatory_hazmat.headline(
					frm,
					__("Gefahrstoffprofil fehlt — Chargenanlage wird abgelehnt"),
					"red",
					"alert-octagon"
				);
			}
			return;
		}
		frappe.db.get_doc("Hazmat Profile", frm.doc.rw_hazmat_profile).then((profile) =>
			rheinwerk_mes.regulatory_hazmat.show_chip(
				frm,
				{
					profile: profile.name,
					storage_class: profile.storage_class,
					icon: rheinwerk_mes.regulatory_hazmat.ACUTE_CLASSES.includes(profile.storage_class)
						? "alert-octagon"
						: "alert-triangle",
					label: `${profile.un_number} · ${__("Lagerklasse {0} — {1}", [
						profile.storage_class,
						profile.storage_class_designation,
					])}`,
				},
				[
					profile.signal_word,
					profile.sds_reference ? __("SDB {0}", [profile.sds_reference]) : "",
					profile.water_hazard_class ? __("WGK {0}", [profile.water_hazard_class]) : "",
				]
			)
		);
	},
});
