// Recipe governance pill on the anchor BOM form (W1-4, URS-W1-014 design conformance).
//
// The anchor DocType is never forked: this client extension only reads the `rw_gov_state`
// Custom Field this app owns and renders it as the standard status pill (colour + label,
// never colour-only) plus a shortcut to the governance record. Colours follow the design
// skill's signal palette: amber = hold/checked, green = released/accepted, red = declined,
// grey = draft/outdated.

frappe.provide("rheinwerk_mes.recipe_isa88");

rheinwerk_mes.recipe_isa88.GOV_STATE_COLOURS = {
	Draft: "gray",
	Checked: "orange",
	Accepted: "green",
	Outdated: "gray",
	Declined: "red",
};

frappe.ui.form.on("BOM", {
	refresh(frm) {
		const state = frm.doc.rw_gov_state;
		if (!state) {
			return;
		}
		frm.page.set_indicator(
			__("Freigabestatus: {0}", [__(state)]),
			rheinwerk_mes.recipe_isa88.GOV_STATE_COLOURS[state] || "gray"
		);
		frm.add_custom_button(__("Freigabedatensatz"), () =>
			frappe.set_route("Form", "Recipe Governance", frm.doc.name)
		);
	},
});
