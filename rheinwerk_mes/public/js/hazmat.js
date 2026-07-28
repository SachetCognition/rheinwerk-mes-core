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

// The chip is a permanent headline alert, not a dashboard indicator: the anchor forms are
// tabbed, so the dashboard's stats area is not on screen where hazmat has to be seen. Icon,
// label and colour are always rendered together, and `facets` (batch override, SDS
// reference) stay on the same line rather than behind a disclosure.
//
// Glyphs for the signal icons `contracts.signal_for_storage_class` returns; the Trace Ribbon
// stylesheet renders the same three via `data-icon`.
rheinwerk_mes.regulatory_hazmat.GLYPHS = {
	"alert-octagon": "⛔",
	"alert-triangle": "⚠",
	info: "ℹ",
};

rheinwerk_mes.regulatory_hazmat.headline = function (frm, label, colour, icon, facets) {
	const parts = [label]
		.concat(facets || [])
		.filter(Boolean)
		.map((part) => frappe.utils.escape_html(part));
	const glyph = rheinwerk_mes.regulatory_hazmat.GLYPHS[icon] || "";
	frm.dashboard.set_headline_alert(
		`<span aria-hidden="true">${glyph}</span> <span class="rw-hazmat-id">${parts.join(" · ")}</span>`,
		colour,
		true
	);
};

rheinwerk_mes.regulatory_hazmat.show_chip = function (frm, chip, facets) {
	if (!chip) {
		return;
	}
	rheinwerk_mes.regulatory_hazmat.headline(
		frm,
		__("Gefahrstoff: {0}", [chip.label]),
		rheinwerk_mes.regulatory_hazmat.colour(chip.storage_class),
		chip.icon || "alert-octagon",
		facets
	);
	if (chip.profile) {
		frm.add_custom_button(__("Gefahrstoffprofil"), () =>
			frappe.set_route("Form", "Hazmat Profile", chip.profile)
		);
	}
};
