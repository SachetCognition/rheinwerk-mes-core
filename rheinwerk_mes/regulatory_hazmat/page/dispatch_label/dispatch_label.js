// Versandetikett Gefahrgut — dispatch station label preview (W3-6 · URS-W3-018).
//
// Terminal Card pattern at the dispatch station: Terminal mode by default (48 px targets,
// 18 px base — the tokens of rheinwerk_mes/public/css/shopfloor.css, switchable with F2),
// an always-focused scan field that accepts a handling unit (HU-000123) or a batch, and one
// giant primary action (print). An incomplete ADR profile is shown as a blocking gate card
// naming rule, record and resolution — the same verdict the dispatch guard will apply, so
// the clerk learns it before the lorry waits, never as a dismissable toast.
// All strings go through __(); dates DD.MM.YYYY, mass in kg.

frappe.pages["dispatch-label"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Versandetikett Gefahrgut"),
		single_column: true,
	});
	new rheinwerk.DispatchLabel(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.DispatchLabel = class DispatchLabel {
	constructor(page) {
		this.page = page;
		this.mode = "Terminal";
		this.label = null;
		this.render_shell();
		this.bind_keyboard();
		this.set_mode(this.mode);
		const batch = frappe.utils.get_url_arg("batch") || frappe.get_route()[1];
		if (batch) {
			this.load_scan(batch);
		}
		this.focus_scan();
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-terminal rw-dispatch" data-mode="Terminal">
				<header class="rw-terminal__header">
					<span class="rw-dispatch__station">${__("Versandstation")}</span>
					<span class="rw-dispatch__focus rw-mono" data-ref="focus">${__("Keine Charge")}</span>
					<span class="rw-pill" data-ref="pill"></span>
					<button class="rw-btn rw-btn--ghost" data-action="toggle-mode">${__("Dichtemodus (F2)")}</button>
				</header>
				<section class="rw-terminal__scan">
					<label for="rw-dispatch-scan">${__("Scannen")}</label>
					<input id="rw-dispatch-scan" class="rw-scan rw-mono" autocomplete="off" data-ref="scan"
						placeholder="${__("Ladeeinheit oder Charge scannen")}" />
					<p class="rw-scan__error" data-ref="scan-error" role="alert" hidden></p>
				</section>
				<section class="rw-dispatch__gate" data-ref="gate" role="alert" hidden></section>
				<section class="rw-dispatch__label" data-ref="label"></section>
				<footer class="rw-dispatch__actions">
					<button class="rw-btn rw-btn--primary rw-dispatch__print" data-action="print" disabled>
						${__("Etikett drucken")}
					</button>
					<span class="rw-dispatch__hint">${__("Enter: drucken · Esc: zurücksetzen · F2: Dichtemodus")}</span>
				</footer>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$scan = this.$body.find('[data-ref="scan"]');
		this.$gate = this.$body.find('[data-ref="gate"]');
		this.$label = this.$body.find('[data-ref="label"]');
		this.$print = this.$body.find('[data-action="print"]');
		this.$body.on("click", '[data-action="toggle-mode"]', () => this.toggle_mode());
		this.$body.on("click", '[data-action="print"]', () => this.print());
		this.$scan.on("change", () => this.load_scan(this.$scan.val()));
		this.$scan.on("blur", () => setTimeout(() => this.focus_scan(), 0));
	}

	focus_scan() {
		this.$scan.trigger("focus");
	}

	bind_keyboard() {
		$(document).on("keydown.rw-dispatch", (event) => {
			if (event.key === "F2") {
				event.preventDefault();
				this.toggle_mode();
			} else if (event.key === "Escape") {
				this.reset();
			} else if (event.key === "Enter" && this.label && this.label.complete) {
				event.preventDefault();
				this.print();
			}
		});
	}

	toggle_mode() {
		this.set_mode(this.mode === "Terminal" ? "Desk" : "Terminal");
	}

	// Terminal mode enlarges, it never hides: both modes render the same label fields.
	set_mode(mode) {
		this.mode = mode;
		this.$body.attr("data-mode", mode);
	}

	reset() {
		this.$scan.val("");
		this.$body.find('[data-ref="scan-error"]').attr("hidden", true);
		this.focus_scan();
	}

	// Progress sits on the control that was pressed (no dead air, no global spinner).
	set_busy(busy) {
		this.$scan.prop("disabled", busy);
		this.$label.attr("aria-busy", busy ? "true" : "false");
	}

	load_scan(code) {
		if (!code) {
			return;
		}
		this.set_busy(true);
		frappe.call({
			method: "rheinwerk_mes.regulatory_hazmat.dispatch.scan_for_dispatch",
			args: { code },
			callback: (r) => {
				this.set_busy(false);
				this.$scan.val("");
				this.focus_scan();
				const result = r.message || {};
				if (!result.recognised) {
					this.show_scan_error(result.message || __("Barcode {0} ist nicht bekannt.", [code]));
					return;
				}
				this.$body.find('[data-ref="scan-error"]').attr("hidden", true);
				if (!result.label_data) {
					this.show_scan_error(__("Zu {0} ist keine Charge gebucht.", [this.esc(result.name)]));
					return;
				}
				this.render_label(result.label_data, result);
			},
			error: () => this.set_busy(false),
		});
	}

	show_scan_error(message) {
		this.$body.find('[data-ref="scan-error"]').text(message).removeAttr("hidden");
	}

	render_label(label, scan) {
		this.label = label;
		this.$body.find('[data-ref="focus"]').text(
			scan.kind === "handling_unit"
				? __("Ladeeinheit {0} · Charge {1}", [scan.name, label.batch])
				: __("Charge {0}", [label.batch])
		);
		const chip = label.chip;
		this.$body
			.find('[data-ref="pill"]')
			.attr("data-tone", chip ? chip.tone : null)
			.text(chip ? chip.label : __("kein Gefahrstoff"));
		this.$print.prop("disabled", !label.complete);
		this.render_gate(label);
		frappe.call({
			method: "rheinwerk_mes.regulatory_hazmat.labels.dispatch_label_html",
			args: { batch: label.batch, warehouse: label.warehouse, handling_unit: label.handling_unit },
			callback: (r) => this.$label.html(r.message || ""),
		});
	}

	// A hard gate looks hard: the refusal names rule, record and resolution and it stays on
	// screen until the data is fixed — printing is disabled while it shows.
	render_gate(label) {
		if (label.complete) {
			this.$gate.attr("hidden", true).empty();
			return;
		}
		this.$gate.html(`
			<h2>${__("Versand abgelehnt: ADR-Daten unvollständig")}</h2>
			<p><b>${__("Regel:")}</b> ${__(
				"Gefahrgut darf nur mit vollständigen ADR-Transportdaten versandt werden (UN-Nummer, offizielle Benennung, ADR-Klasse, Verpackungsgruppe)."
			)}</p>
			<p><b>${__("Datensatz:")}</b> ${__("Artikel {0}, Charge {1} — fehlende Angaben: {2}", [
				this.esc(label.item),
				this.esc(label.batch),
				this.esc((label.missing_labels || []).join(", ")),
			])}</p>
			<p><b>${__("Behebung:")}</b> ${__(
				"Gefahrstoffprofil vervollständigen (Technologe, Feld „ADR-Transportdaten“) und den Versand erneut buchen."
			)}</p>
		`).removeAttr("hidden");
	}

	print() {
		if (!this.label || !this.label.complete) {
			return;
		}
		window.print();
	}
};
