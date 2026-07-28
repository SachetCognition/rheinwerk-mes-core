// Interface health — plain-language KPI tile → dense ERP message queue (W3-3 · URS-W3-014).
//
// Top: one sentence with a number for B. Vogel ("ERP-Nachrichten mit Handlungsbedarf: 1") plus
// three counters (Fehlerwarteschlange, Zurückgehalten, Wartend) and the oldest unprocessed
// message. Clicking the tile drills into the dense table P. Krüger works in: message id, type,
// reference, machine-readable reason, attempts, timestamps and — for authorised users — replay.
// Every string goes through __() (German-first); timestamps render DD.MM.YYYY HH:mm.

frappe.pages["interface-health"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Schnittstellen-Gesundheit"),
		single_column: true,
	});
	new rheinwerk.InterfaceHealth(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.InterfaceHealth = class InterfaceHealth {
	constructor(page) {
		this.page = page;
		this.model = null;
		this.filter = { status: "", message_type: "" };
		this.render_shell();
		this.load();
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-boundary">
				<section class="rw-boundary__tile" data-ref="tile" role="button" tabindex="0"
					aria-label="${__("Zur Fehlerwarteschlange")}"></section>
				<section class="rw-boundary__counters" data-ref="counters"></section>
				<header class="rw-boundary__bar">
					<label for="rw-bnd-status">${__("Nachrichtenstatus")}</label>
					<select id="rw-bnd-status" data-ref="status">
						<option value="">${__("Alle offenen")}</option>
						<option value="Abgelehnt">${__("Abgelehnt")}</option>
						<option value="Zurückgehalten">${__("Zurückgehalten")}</option>
						<option value="In Warteschlange">${__("In Warteschlange")}</option>
						<option value="Zugestellt">${__("Zugestellt")}</option>
						<option value="Verarbeitet">${__("Verarbeitet")}</option>
					</select>
					<label for="rw-bnd-type">${__("Nachrichtentyp")}</label>
					<select id="rw-bnd-type" data-ref="type">
						<option value="">${__("Alle")}</option>
						<option value="orders-in">${__("Bedarf eingehend")}</option>
						<option value="confirmation-out">${__("Fertigmeldung ausgehend")}</option>
						<option value="gl-posting-out">${__("Buchung ausgehend")}</option>
					</select>
					<button class="rw-btn" data-action="reload">${__("Aktualisieren")}</button>
					<button class="rw-btn rw-btn--primary" data-action="replay-all">
						${__("Warteschlange erneut senden")}
					</button>
				</header>
				<section class="rw-boundary__queue" data-ref="queue"></section>
			</div>
		`);
		this.page.main.append(this.$body);

		this.$body.on("click", '[data-action="reload"]', () => this.load());
		this.$body.on("click", '[data-action="replay-all"]', () => this.replay_all());
		this.$body.on("change", '[data-ref="status"], [data-ref="type"]', () => this.apply_filter());
		this.$body.on("click", '[data-ref="tile"]', () => this.drilldown());
		this.$body.on("keydown", '[data-ref="tile"]', (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				this.drilldown();
			}
		});
		this.$body.on("click", "[data-replay]", (event) => this.replay($(event.currentTarget).attr("data-replay")));
	}

	load() {
		frappe.call({ method: "rheinwerk_mes.integration.boundary.health.dashboard" }).then((response) => {
			this.model = response.message;
			this.render();
		});
	}

	apply_filter() {
		this.filter.status = this.$body.find('[data-ref="status"]').val() || "";
		this.filter.message_type = this.$body.find('[data-ref="type"]').val() || "";
		frappe
			.call({
				method: "rheinwerk_mes.integration.boundary.health.queue",
				args: this.filter,
			})
			.then((response) => {
				this.model.queue = response.message;
				this.render_queue();
			});
	}

	drilldown() {
		// The tile is the entry point: it filters the dense queue down to exactly the
		// messages that need attention (rejected + held).
		this.$body.find('[data-ref="status"]').val("Abgelehnt");
		this.apply_filter();
	}

	render() {
		this.render_tile();
		this.render_counters();
		this.render_queue();
	}

	render_tile() {
		const tile = this.model.tile;
		this.$body
			.find('[data-ref="tile"]')
			.attr("data-tone", tile.tone)
			.html(`
				<span class="rw-boundary__headline">${this.esc(tile.headline)}</span>
				<span class="rw-boundary__detail">${this.esc(tile.detail)}</span>
				<span class="rw-boundary__cta">${__("Zur Fehlerwarteschlange")}</span>
			`);
	}

	render_counters() {
		const m = this.model.metrics;
		const oldest = m.oldest_unprocessed;
		const cells = [
			[__("Nachrichten insgesamt"), m.total],
			[__("Fehlerwarteschlange"), m.error_queue_depth],
			[__("Zurückgehalten"), m.hold_queue_depth],
			[__("Wartend auf Zustellung"), m.outbox_depth],
			[__("Vertragsversion"), m.contract_version],
		]
			.map(
				([label, value]) => `
				<div class="rw-boundary__counter">
					<span class="rw-boundary__counter-label">${this.esc(label)}</span>
					<span class="rw-boundary__counter-value rw-mono">${this.esc(value)}</span>
				</div>`
			)
			.join("");
		const oldest_html = oldest
			? `<div class="rw-boundary__counter rw-boundary__counter--wide">
					<span class="rw-boundary__counter-label">${__("Älteste unverarbeitete Nachricht")}</span>
					<span class="rw-boundary__counter-value rw-mono">
						${this.esc(oldest.message_id)} · ${this.esc(oldest.first_seen_display)}
					</span>
				</div>`
			: `<div class="rw-boundary__counter rw-boundary__counter--wide">
					<span class="rw-boundary__counter-label">${__("Älteste unverarbeitete Nachricht")}</span>
					<span class="rw-boundary__counter-value">${__("Keine offene Nachricht")}</span>
				</div>`;
		this.$body.find('[data-ref="counters"]').html(cells + oldest_html);
	}

	render_queue() {
		const rows = this.model.queue || [];
		const labels = this.model.labels.message_types;
		if (!rows.length) {
			this.$body
				.find('[data-ref="queue"]')
				.html(`<p class="rw-boundary__empty">${__("Keine Nachrichten in dieser Auswahl.")}</p>`);
			return;
		}
		const body = rows
			.map(
				(row) => `
			<tr>
				<td class="rw-mono">${this.esc(row.message_id)}</td>
				<td>${this.esc(labels[row.message_type] || row.message_type)}</td>
				<td class="rw-mono">${this.esc(row.external_reference)}</td>
				<td><span class="rw-boundary__pill" data-status="${this.esc(row.message_state)}">${this.esc(row.message_state)}</span></td>
				<td class="rw-mono">${this.esc(row.reason_code)}</td>
				<td>${this.esc(row.reason)}</td>
				<td class="rw-mono">${this.esc(row.attempts)}</td>
				<td class="rw-mono">${this.esc(row.first_seen_display)}</td>
				<td class="rw-mono">${this.esc(row.last_attempt_display)}</td>
				<td>${
					this.model.can_replay
						? `<button class="rw-btn rw-btn--small" data-replay="${this.esc(row.name)}">${__("Erneut verarbeiten")}</button>`
						: ""
				}</td>
			</tr>`
			)
			.join("");
		this.$body.find('[data-ref="queue"]').html(`
			<table class="rw-boundary__table">
				<thead>
					<tr>
						<th>${__("Nachricht")}</th>
						<th>${__("Typ")}</th>
						<th>${__("Referenz")}</th>
						<th>${__("Nachrichtenstatus")}</th>
						<th>${__("Grundschlüssel")}</th>
						<th>${__("Grund")}</th>
						<th>${__("Versuche")}</th>
						<th>${__("Erstmals gesehen")}</th>
						<th>${__("Letzter Versuch")}</th>
						<th>${__("Aktion")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		`);
	}

	replay(name) {
		frappe
			.call({ method: "rheinwerk_mes.integration.boundary.health.replay", args: { name } })
			.then((response) => {
				const outcome = response.message || {};
				frappe.show_alert({
					message: __("Nachricht {0}: {1}", [name, outcome.detail || outcome.message_state]),
					indicator: outcome.message_state === "Zugestellt" || outcome.message_state === "Verarbeitet" ? "green" : "orange",
				});
				this.load();
			});
	}

	replay_all() {
		frappe.call({ method: "rheinwerk_mes.integration.boundary.health.replay_all" }).then((response) => {
			const result = response.message || {};
			frappe.show_alert({
				message: __("Zugestellt: {0} · Weiterhin in Warteschlange: {1}", [
					result.delivered || 0,
					result.queued || 0,
				]),
				indicator: result.queued ? "orange" : "green",
			});
			this.load();
		});
	}
};
