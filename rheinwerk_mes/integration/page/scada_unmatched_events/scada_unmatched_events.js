// Unmatched OPC-UA events — the planner's disposition queue (W3-5 · URS-W3-015 AC-2).
//
// Command-Dashboard pattern (design skill § "Layout patterns" 3): a plain-language headline
// tile drills into a dense professional table. Identifiers (tag address, work-centre code,
// order) render mono/tabular; timestamps DD.MM.YYYY HH:MM and quantities in kg come
// pre-formatted from the server so client and server never disagree on the locale.
// Every string goes through __(); the page styles itself, so no shared CSS asset is touched.

frappe.pages["scada-unmatched-events"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Nicht zugeordnete OPC-UA-Ereignisse"),
		single_column: true,
	});
	new rheinwerk.ScadaUnmatchedEvents(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.ScadaUnmatchedEvents = class ScadaUnmatchedEvents {
	constructor(page) {
		this.page = page;
		this.model = { rows: [], depth: 0 };
		this.inject_styles();
		this.render_shell();
		this.load();
	}

	inject_styles() {
		if (document.getElementById("rw-scada-styles")) {
			return;
		}
		$(`<style id="rw-scada-styles">
			.rw-scada__tile { border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
				padding: 12px 16px; margin-bottom: 12px; background: var(--fg-color); }
			.rw-scada__tile b { font-size: 20px; }
			.rw-scada__table { width: 100%; border-collapse: collapse; }
			.rw-scada__table th { position: sticky; top: 0; background: var(--fg-color); text-align: left;
				font-weight: 600; border-bottom: 1px solid var(--border-color); padding: 8px; }
			.rw-scada__table td { border-bottom: 1px solid var(--border-color); padding: 8px;
				vertical-align: top; }
			.rw-scada__table td.rw-num { text-align: right; font-variant-numeric: tabular-nums; }
			.rw-mono { font-family: var(--font-stack-mono, 'IBM Plex Mono', monospace);
				font-variant-numeric: tabular-nums; }
			.rw-scada__late { border: 1px solid var(--border-color); border-radius: 10px;
				padding: 1px 8px; font-size: 11px; }
			.rw-scada__empty { padding: 24px; color: var(--text-muted); }
		</style>`).appendTo(document.head);
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-scada">
				<div class="rw-scada__tile" data-ref="tile"></div>
				<div data-ref="table"></div>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$tile = this.$body.find('[data-ref="tile"]');
		this.$table = this.$body.find('[data-ref="table"]');
		this.page.set_primary_action(__("Aktualisieren"), () => this.load());
		this.page.add_inner_button(__("Tag-Zuordnungen"), () =>
			frappe.set_route("List", "OPC UA Tag Mapping")
		);
		this.page.add_inner_button(__("Simulator abspielen"), () => this.play_fixture());
		this.$body.on("click", '[data-action="assign"]', (event) =>
			this.assign($(event.currentTarget).attr("data-event"))
		);
		this.$body.on("click", '[data-action="discard"]', (event) =>
			this.discard($(event.currentTarget).attr("data-event"))
		);
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	load() {
		frappe.call("rheinwerk_mes.integration.scada.unmatched.queue").then(({ message }) => {
			this.model = message;
			this.render();
		});
	}

	play_fixture() {
		frappe
			.call("rheinwerk_mes.integration.scada.api.play_fixture")
			.then(({ message }) => {
				frappe.show_alert({ message: message.message, indicator: "blue" });
				this.load();
			});
	}

	render() {
		this.$tile.html(`
			<div>${__("Ereignisse ohne laufenden Auftrag")}</div>
			<b>${this.model.depth}</b>
			<div class="text-muted">${__("Zur Klärung durch die Planung — keine Meldung wird verworfen.")}</div>
		`);

		if (!this.model.rows.length) {
			this.$table.html(`<div class="rw-scada__empty">${this.esc(this.model.empty_hint)}</div>`);
			return;
		}

		const head = [
			__("Anlagenzeitstempel"),
			__("OPC-UA-Adresse"),
			__("Arbeitsplatz"),
			__("Ereignisart"),
			__("Menge"),
			__("Grund"),
			__("Klärung"),
		]
			.map((label) => `<th>${label}</th>`)
			.join("");

		const rows = this.model.rows
			.map(
				(row) => `
				<tr>
					<td class="rw-mono">${this.esc(row.equipment_timestamp_display)}
						${row.is_late ? `<span class="rw-scada__late">${__("nachgeliefert")}</span>` : ""}</td>
					<td class="rw-mono">${this.esc(row.tag_address)}</td>
					<td class="rw-mono">${this.esc(row.work_centre_code)}</td>
					<td>${this.esc(__(row.event_type))}</td>
					<td class="rw-num">${this.esc(row.value_display)}</td>
					<td>${this.esc(row.unmatched_reason)}</td>
					<td>
						<button class="btn btn-xs btn-default" data-action="assign"
							data-event="${this.esc(row.name)}">${__("Auftrag zuordnen")}</button>
						<button class="btn btn-xs btn-default" data-action="discard"
							data-event="${this.esc(row.name)}">${__("Verwerfen")}</button>
					</td>
				</tr>`
			)
			.join("");

		this.$table.html(
			`<table class="rw-scada__table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`
		);
	}

	assign(event) {
		const dialog = new frappe.ui.Dialog({
			title: __("Ereignis einem Auftrag zuordnen"),
			fields: [
				{
					fieldname: "work_order",
					fieldtype: "Link",
					options: "Work Order",
					label: __("Fertigungsauftrag"),
					reqd: 1,
				},
				{ fieldname: "note", fieldtype: "Small Text", label: __("Klärungsvermerk") },
			],
			primary_action_label: __("Zuordnen"),
			primary_action: (values) => {
				frappe
					.call("rheinwerk_mes.integration.scada.unmatched.assign_to_order", {
						event,
						work_order: values.work_order,
						note: values.note,
					})
					.then(() => {
						dialog.hide();
						this.load();
					});
			},
		});
		dialog.show();
	}

	discard(event) {
		const dialog = new frappe.ui.Dialog({
			title: __("Ereignis verwerfen"),
			fields: [
				{ fieldname: "note", fieldtype: "Small Text", label: __("Begründung"), reqd: 1 },
			],
			primary_action_label: __("Verwerfen"),
			primary_action: (values) => {
				frappe
					.call("rheinwerk_mes.integration.scada.unmatched.discard", {
						event,
						note: values.note,
					})
					.then(() => {
						dialog.hide();
						this.load();
					});
			},
		});
		dialog.show();
	}
};
