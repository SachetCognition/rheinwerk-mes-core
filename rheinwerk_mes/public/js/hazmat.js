// Shared hazmat chip helpers (W2-7 · URS-W2-024).
//
// One chip component for every surface that shows hazmat data — Item form, Batch form,
// stock views and the Trace Ribbon — so the status pill really is "the status API of the UI"
// (design skill component rules): icon + label + colour, never colour alone.

frappe.provide("rheinwerk_mes.regulatory_hazmat");

// Lagerklassen with an acute hazard (TRGS 510) carry the red signal; toxic/corrosive classes
// amber; the non-CLP storage classes 10–13 are informational. Mirrors
// `rheinwerk_mes/regulatory_hazmat/contracts.py` — the server model is authoritative.
rheinwerk_mes.regulatory_hazmat.ACUTE_CLASSES = [
	"1",
	"2A",
	"2B",
	"3",
	"4.1A",
	"4.1B",
	"4.2",
	"4.3",
	"5.1A",
	"5.1B",
	"5.1C",
	"5.2",
	"6.1A",
	"6.1B",
	"6.2",
	"7",
];
rheinwerk_mes.regulatory_hazmat.ADVISORY_CLASSES = ["6.1C", "6.1D", "8A", "8B"];

rheinwerk_mes.regulatory_hazmat.colour = function (storage_class) {
	if (rheinwerk_mes.regulatory_hazmat.ACUTE_CLASSES.includes(storage_class)) {
		return "red";
	}
	if (rheinwerk_mes.regulatory_hazmat.ADVISORY_CLASSES.includes(storage_class)) {
		return "orange";
	}
	return "blue";
};

rheinwerk_mes.regulatory_hazmat.show_chip = function (frm, chip) {
	if (!chip) {
		return;
	}
	frm.dashboard.add_indicator(
		__("Gefahrstoff: {0}", [chip.label]),
		rheinwerk_mes.regulatory_hazmat.colour(chip.storage_class)
	);
	if (chip.profile) {
		frm.add_custom_button(__("Gefahrstoffprofil"), () =>
			frappe.set_route("Form", "Hazmat Profile", chip.profile)
		);
	}
};
