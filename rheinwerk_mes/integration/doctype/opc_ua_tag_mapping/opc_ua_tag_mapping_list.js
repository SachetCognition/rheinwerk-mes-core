// Tag-mapping admin — Desk-mode table for the technologist (W3-5 · URS-W3-016).
//
// Design skill § "Typography — Identifiers": tag addresses and work-centre codes are
// identifiers, so they render in tabular mono and stay column-aligned; § "Component rules —
// Tables": inline state pill per row. German-first, every string through __().

frappe.listview_settings["OPC UA Tag Mapping"] = {
	add_fields: ["enabled", "event_type", "work_centre_code", "tag_address"],
	hide_name_column: true,

	get_indicator(doc) {
		return doc.enabled
			? [__("Aktiv"), "green", "enabled,=,1"]
			: [__("Inaktiv"), "gray", "enabled,=,0"];
	},

	formatters: {
		// The subject cell escapes what the formatter returns, so the address is handed over
		// verbatim and gets its mono treatment from the style rule below.
		tag_address(value) {
			return value == null ? "" : String(value);
		},
		work_centre_code(value) {
			return rheinwerk_scada_mono(value);
		},
		event_type(value) {
			return frappe.utils.escape_html(__(value || ""));
		},
	},

	onload(listview) {
		frappe.dom.set_style(
			`.list-subject a[data-doctype="OPC UA Tag Mapping"] {
				font-family: var(--font-stack-mono, 'IBM Plex Mono', monospace);
				font-variant-numeric: tabular-nums;
			}
			[data-page-route="List/OPC UA Tag Mapping/List"] .list-row-col.list-subject { flex: 2.4; }`,
			"rheinwerk-scada-mapping-mono"
		);
		listview.page.add_inner_button(__("Simulator abspielen"), () =>
			frappe
				.call("rheinwerk_mes.integration.scada.api.play_fixture")
				.then(({ message }) => frappe.show_alert({ message: message.message, indicator: "blue" }))
		);
		listview.page.add_inner_button(__("Nicht zugeordnete Ereignisse"), () =>
			frappe.set_route("scada-unmatched-events")
		);
	},
};

function rheinwerk_scada_mono(value) {
	const text = frappe.utils.escape_html(value == null ? "" : String(value));
	return `<span style="font-family: var(--font-stack-mono, 'IBM Plex Mono', monospace);
		font-variant-numeric: tabular-nums;">${text}</span>`;
}
