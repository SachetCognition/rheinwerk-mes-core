// Tag-mapping form — mono identifiers and the resolved work centre (W3-5 · URS-W3-016).

frappe.ui.form.on("OPC UA Tag Mapping", {
	refresh(frm) {
		["tag_address", "work_centre_code"].forEach((field) => {
			const $input = frm.get_field(field).$input;
			if ($input) {
				$input.css({ "font-family": "var(--font-stack-mono, 'IBM Plex Mono', monospace)" });
			}
		});
		frm.set_df_property(
			"work_centre_code",
			"description",
			__("Arbeitsplatzschlüssel als Linie/Arbeitsplatz, z. B. LINE-1/MIX-01 (CDM-08).")
		);
	},
});
