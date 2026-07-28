// Inspection queue — Work Queue → Detail for the quality inspector (W2-4 · URS-W2-015).
//
// Left: the due inspections (batch chip, item, type, due indication). Right: the selected
// inspection with its reading inputs — units suffixed *inside* the input, label above the
// field, inline validation on blur, entered values preserved when a submit fails.
// Keyboard: arrows move the selection, Enter opens the detail, Esc closes it, `?` opens the
// shortcut sheet. Every string goes through __() (German-first); dates DD.MM.YYYY.

frappe.pages["inspection-queue"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Prüfliste"),
		single_column: true,
	});
	new rheinwerk.InspectionQueue(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.InspectionQueue = class InspectionQueue {
	constructor(page) {
		this.page = page;
		this.model = null;
		this.detail = null;
		this.selected = 0;
		this.entries = {};
		this.render_shell();
		this.bind_keyboard();
		this.load();
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-queue">
				<header class="rw-queue__bar">
					<label for="rw-queue-type">${__("Prüfart")}</label>
					<select id="rw-queue-type" data-ref="type">
						<option value="">${__("Alle")}</option>
						<option value="Incoming">${__("Wareneingang")}</option>
						<option value="Outgoing">${__("Warenausgang")}</option>
						<option value="In Process">${__("Fertigungsbegleitend")}</option>
					</select>
					<label for="rw-queue-batch">${__("Charge")}</label>
					<input id="rw-queue-batch" class="rw-mono" data-ref="batch" autocomplete="off" />
					<button class="rw-btn" data-action="reload">${__("Aktualisieren")}</button>
					<span class="rw-queue__hint">${__("Pfeiltasten: Auswahl · Enter: Detail · Esc: schließen · ?: Tastenkürzel")}</span>
				</header>
				<div class="rw-queue__split">
					<section class="rw-queue__list" data-ref="list" role="list"
						aria-label="${__("Fällige Prüfungen")}"></section>
					<section class="rw-queue__detail" data-ref="detail"></section>
				</div>
				<section class="rw-queue__findings" data-ref="findings"></section>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$list = this.$body.find('[data-ref="list"]');
		this.$detail = this.$body.find('[data-ref="detail"]');
		this.$findings = this.$body.find('[data-ref="findings"]');
		this.$body.on("click", '[data-action="reload"]', () => this.load());
		this.$body.on("click", "[data-row]", (event) => {
			this.selected = Number($(event.currentTarget).attr("data-index"));
			this.open_selected();
		});
		this.$body.on("click", '[data-action="create"]', () => this.create_inspection());
		this.$body.on("click", '[data-action="save"]', () => this.save(false));
		this.$body.on("click", '[data-action="submit"]', () => this.save(true));
		// Inline validation on blur; the entered value itself is never discarded (AC-2).
		this.$body.on("blur", "[data-parameter]", (event) => this.validate_reading($(event.target)));
		this.$body.on("input", "[data-parameter]", (event) => {
			const $input = $(event.target);
			this.entries[$input.attr("data-parameter")] = $input.val();
		});
	}

	bind_keyboard() {
		$(document).on("keydown.rwqueue", (event) => {
			if (!this.$body.is(":visible")) {
				return;
			}
			const rows = (this.model && this.model.rows) || [];
			if (event.key === "ArrowDown" || event.key === "ArrowRight") {
				this.selected = Math.min(this.selected + 1, rows.length - 1);
				this.render_list();
			} else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
				this.selected = Math.max(this.selected - 1, 0);
				this.render_list();
			} else if (event.key === "Enter") {
				this.open_selected();
			} else if (event.key === "Escape") {
				this.detail = null;
				this.render_detail();
			} else if (event.key === "?") {
				frappe.msgprint({
					title: __("Tastenkürzel"),
					message: __("↑ ↓ Auswahl · Enter Detail öffnen · Esc Detail schließen"),
				});
			}
		});
	}

	load() {
		const filters = {
			inspection_type: this.$body.find('[data-ref="type"]').val() || null,
			batch: this.$body.find('[data-ref="batch"]').val() || null,
		};
		frappe.call("rheinwerk_mes.quality.queue.inspection_queue", filters).then((response) => {
			this.model = response.message;
			this.selected = 0;
			this.render_list();
			this.render_findings();
		});
	}

	render_list() {
		const rows = (this.model && this.model.rows) || [];
		if (!rows.length) {
			const empty = (this.model && this.model.empty_state) || {};
			this.$list.html(`<div class="rw-queue__empty">
				<h2>${this.esc(empty.title || __("Keine Prüfungen fällig"))}</h2>
				<p>${this.esc(empty.hint || "")}</p>
			</div>`);
			this.$detail.empty();
			return;
		}
		this.$list.html(
			rows
				.map(
					(row, index) => `<article class="rw-queue__row" role="listitem" tabindex="-1"
						data-row="1" data-index="${index}"
						aria-current="${index === this.selected ? "true" : "false"}">
					<h3 class="rw-mono">${this.esc(row.batch)}</h3>
					<p>${this.esc(row.item)} · ${this.esc(row.type_label)}</p>
					<p class="rw-queue__due">${this.esc(row.due_reason)} ${this.esc(row.due_date)}</p>
					<span class="rw-pill rw-pill--${row.chip && row.chip.qa_state === "Released" ? "green" : "amber"}">
						<span class="rw-pill__label">${this.esc(row.chip ? row.chip.qa_state_label : "")}</span>
					</span>
				</article>`
				)
				.join("")
		);
	}

	current_row() {
		const rows = (this.model && this.model.rows) || [];
		return rows[this.selected];
	}

	open_selected() {
		const row = this.current_row();
		if (!row) {
			return;
		}
		if (!row.inspection) {
			this.detail = { create_for: row };
			this.render_detail();
			return;
		}
		frappe
			.call("rheinwerk_mes.quality.queue.inspection_detail", { inspection: row.inspection })
			.then((response) => {
				this.detail = response.message;
				this.entries = {};
				(this.detail.readings || []).forEach((reading) => {
					this.entries[reading.parameter] = reading.reading;
				});
				this.render_detail();
			});
	}

	create_inspection() {
		const row = this.current_row();
		frappe
			.call("rheinwerk_mes.quality.inspections.create_inspection", {
				batch: row.batch,
				inspection_type: row.inspection_type,
				work_order: row.production_order,
			})
			.then(() => this.load());
	}

	render_detail() {
		if (!this.detail) {
			this.$detail.empty();
			return;
		}
		if (this.detail.create_for) {
			const row = this.detail.create_for;
			this.$detail.html(`<div class="rw-queue__pane">
				<h2 class="rw-mono">${this.esc(row.batch)}</h2>
				<p>${this.esc(row.item)} · ${this.esc(row.template)}</p>
				<button class="rw-btn" data-action="create">${__("Prüfung anlegen")}</button>
			</div>`);
			return;
		}
		const detail = this.detail;
		this.$detail.html(`<div class="rw-queue__pane">
			<h2 class="rw-mono">${this.esc(detail.inspection)}</h2>
			<p>${this.esc(detail.batch)} · ${this.esc(detail.item)} · ${this.esc(detail.type_label)}</p>
			<form class="rw-form">
				${(detail.readings || [])
					.map(
						(reading) => `<div class="rw-field">
					<label for="rw-r-${this.esc(reading.parameter)}">${this.esc(reading.label)}</label>
					<div class="rw-input-affix">
						<input id="rw-r-${this.esc(reading.parameter)}" data-parameter="${this.esc(reading.parameter)}"
							value="${this.esc(this.entries[reading.parameter] || "")}"
							${detail.submitted ? "readonly" : ""} inputmode="decimal" />
						<span class="rw-input-affix__unit">${this.esc(reading.unit_suffix)}</span>
					</div>
					<p class="rw-field__hint">${__("Spezifikation")}: ${this.esc(reading.limit_text)}</p>
					<p class="rw-field__error" data-error="${this.esc(reading.parameter)}"></p>
				</div>`
					)
					.join("")}
			</form>
			${
				detail.submitted
					? `<p class="rw-queue__status">${this.esc(detail.status_label)}</p>`
					: `<button class="rw-btn rw-btn--ghost" data-action="save">${__("Speichern")}</button>
						<button class="rw-btn" data-action="submit">${__("Buchen")}</button>`
			}
		</div>`);
	}

	reading_spec(parameter) {
		return (this.detail.readings || []).find((reading) => reading.parameter === parameter);
	}

	validate_reading($input) {
		const parameter = $input.attr("data-parameter");
		const spec = this.reading_spec(parameter);
		const value = $input.val();
		const $error = this.$body.find(`[data-error="${parameter}"]`);
		if (!value || !spec || !spec.numeric) {
			$error.text("");
			return true;
		}
		const numeric = Number(String(value).replace(",", "."));
		const inside = !isNaN(numeric) && numeric >= spec.min_value && numeric <= spec.max_value;
		$error.text(inside ? "" : __("Außerhalb der Spezifikation: {0}", [spec.limit_text]));
		return inside;
	}

	save(submit) {
		frappe
			.call("rheinwerk_mes.quality.inspections.enter_readings", {
				inspection: this.detail.inspection,
				readings: this.entries,
				submit: submit ? 1 : 0,
			})
			.then(() => this.load())
			// A failed submit keeps the pane and the entered values (URS-W2-015 AC-2).
			.catch(() => this.render_detail());
	}

	render_findings() {
		const findings = (this.model && this.model.findings) || [];
		if (!findings.length) {
			this.$findings.empty();
			return;
		}
		this.$findings.html(`<h2>${__("Abgelehnt ohne Verwendungsentscheid")}</h2>
			<ul>${findings
				.map(
					(finding) =>
						`<li class="rw-mono">${this.esc(finding.inspection)} · ${this.esc(finding.batch)} — ${this.esc(
							finding.finding
						)}</li>`
				)
				.join("")}</ul>`);
	}
};
