// Schedule board — the planner's line schedule (W3-2 · URS-W3-005, URS-W3-020).
//
// Left: the line's schedules with their state pill (icon + label + tone, never colour
// alone). Right: the sequence of the selected schedule as a dense, virtualized table —
// only the visible rows are in the DOM, so a 200-order schedule renders inside the
// URS-W3-020 budget (≤ 2 s) and scrolls without re-fetching. Every control that can take
// longer than 100 ms (loading a page of rows, approving, rejecting) shows progress on the
// control itself.
// Keyboard: arrows move the selection, Enter opens the order, F freigeben, A ablehnen,
// Esc closes the detail, `?` opens the shortcut sheet. Every string goes through __()
// (German-first); dates DD.MM.YYYY, masses in kg.

frappe.pages["schedule-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Linienplan"),
		single_column: true,
	});
	new rheinwerk.ScheduleBoard(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.ScheduleBoard = class ScheduleBoard {
	constructor(page) {
		this.page = page;
		this.schedules = [];
		this.selected = 0;
		this.head = null;
		this.rows = [];
		this.total = 0;
		this.pending = new Set();
		this.detail = null;
		this.row_height = 32;
		this.page_length = 100;
		this.render_shell();
		this.bind_keyboard();
		this.load_schedules();
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-board">
				<header class="rw-board__bar">
					<label for="rw-board-line">${__("Fertigungslinie")}</label>
					<input id="rw-board-line" class="rw-mono" data-ref="line" autocomplete="off"
						placeholder="LINE-1" />
					<button class="rw-btn" data-action="reload">${__("Aktualisieren")}</button>
					<button class="rw-btn" data-action="approve">${__("Plan freigeben")}</button>
					<button class="rw-btn" data-action="reject">${__("Plan ablehnen")}</button>
					<span class="rw-board__hint">${__(
						"Pfeiltasten: Auswahl · Enter: Auftrag · F: freigeben · A: ablehnen · ?: Tastenkürzel"
					)}</span>
				</header>
				<div class="rw-board__split">
					<section class="rw-board__list" data-ref="list" role="list"
						aria-label="${__("Linienpläne")}"></section>
					<section class="rw-board__plan">
						<div class="rw-board__head" data-ref="head"></div>
						<div class="rw-board__table" data-ref="table" tabindex="0"
							role="table" aria-label="${__("Auftragsfolge")}"></div>
						<div class="rw-board__detail" data-ref="detail"></div>
					</section>
				</div>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$list = this.$body.find('[data-ref="list"]');
		this.$head = this.$body.find('[data-ref="head"]');
		this.$table = this.$body.find('[data-ref="table"]');
		this.$detail = this.$body.find('[data-ref="detail"]');
		this.$body.on("click", '[data-action="reload"]', () => this.load_schedules());
		this.$body.on("click", '[data-action="approve"]', (event) => this.decide($(event.currentTarget), "approve"));
		this.$body.on("click", '[data-action="reject"]', (event) => this.decide($(event.currentTarget), "reject"));
		this.$body.on("click", "[data-schedule]", (event) => {
			this.selected = Number($(event.currentTarget).attr("data-index"));
			this.open_selected();
		});
		this.$body.on("click", "[data-order]", (event) => this.open_order($(event.currentTarget).attr("data-order")));
		this.$table.on("scroll", () => this.paint_rows());
	}

	// Shortcuts must never fire while the planner types a reason or a dialog is open —
	// otherwise every "f" in a justification would open the approval dialog again.
	typing(event) {
		const $target = $(event.target);
		if ($target.is("input, textarea, select, [contenteditable='true']")) {
			return true;
		}
		return $(document.body).hasClass("modal-open") || $(".modal:visible").length > 0;
	}

	bind_keyboard() {
		$(document).on("keydown.rwboard", (event) => {
			if (!this.$body.is(":visible") || this.typing(event)) {
				return;
			}
			if (event.key === "ArrowDown" || event.key === "ArrowRight") {
				this.selected = Math.min(this.selected + 1, this.schedules.length - 1);
				this.render_list();
				this.open_selected();
			} else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
				this.selected = Math.max(this.selected - 1, 0);
				this.render_list();
				this.open_selected();
			} else if (event.key === "Escape") {
				this.detail = null;
				this.render_detail();
			} else if (event.key === "f" || event.key === "F") {
				this.decide(this.$body.find('[data-action="approve"]'), "approve");
			} else if (event.key === "a" || event.key === "A") {
				this.decide(this.$body.find('[data-action="reject"]'), "reject");
			} else if (event.key === "?") {
				frappe.msgprint({
					title: __("Tastenkürzel"),
					message: __("↑ ↓ Auswahl · Enter Auftrag öffnen · F freigeben · A ablehnen · Esc schließen"),
				});
			}
		});
	}

	// Progress on the control itself for anything that may exceed 100 ms (URS-W3-020 AC-2).
	busy($control, key, running) {
		if (running) {
			this.pending.add(key);
			if ($control && $control.length) {
				$control.prop("disabled", true).attr("aria-busy", "true").addClass("rw-btn--busy");
			}
		} else {
			this.pending.delete(key);
			if ($control && $control.length) {
				$control.prop("disabled", false).removeAttr("aria-busy").removeClass("rw-btn--busy");
			}
		}
	}

	load_schedules() {
		const $control = this.$body.find('[data-action="reload"]');
		this.busy($control, "schedules", true);
		frappe
			.call("rheinwerk_mes.manufacturing_core.scheduling.board.line_schedules", {
				production_line: this.$body.find('[data-ref="line"]').val() || null,
			})
			.then((response) => {
				this.schedules = response.message || [];
				this.selected = 0;
				this.render_list();
				this.open_selected();
			})
			.always(() => this.busy($control, "schedules", false));
	}

	current() {
		return this.schedules[this.selected] || null;
	}

	state_pill(row) {
		const icons = { Draft: "○", Approved: "●", Rejected: "✕" };
		const icon = icons[row.schedule_state] || "○";
		return `<span class="rw-pill rw-pill--${this.esc(row.schedule_state_indicator)}">
			<span aria-hidden="true">${icon}</span> ${this.esc(row.schedule_state_label)}</span>`;
	}

	render_list() {
		if (!this.schedules.length) {
			this.$list.html(`<p class="rw-board__empty">${__("Keine Linienpläne vorhanden.")}</p>`);
			return;
		}
		this.$list.html(
			this.schedules
				.map(
					(row, index) => `
			<article class="rw-board__card ${index === this.selected ? "is-selected" : ""}"
				data-schedule="${this.esc(row.name)}" data-index="${index}" role="listitem"
				aria-selected="${index === this.selected}">
				<div class="rw-board__card-top">
					<span class="rw-mono">${this.esc(row.name)}</span>
					${this.state_pill(row)}
				</div>
				<div class="rw-board__card-meta">
					<span class="rw-mono">${this.esc(row.production_line)}</span>
					<span>${__("Planbeginn")}: ${this.esc(row.planned_start)}</span>
					${row.is_operative ? `<span class="rw-board__flag">${__("operativ")}</span>` : ""}
				</div>
			</article>`
				)
				.join("")
		);
	}

	open_selected() {
		const row = this.current();
		this.detail = null;
		this.render_detail();
		if (!row) {
			this.$head.empty();
			this.$table.empty();
			return;
		}
		this.render_list();
		frappe
			.call("rheinwerk_mes.manufacturing_core.scheduling.board.board_head", { schedule: row.name })
			.then((response) => {
				this.head = response.message;
				this.render_head();
			});
		this.rows = [];
		this.total = 0;
		this.load_rows(0);
	}

	// Virtualized fetch: one page of rows per request, cached by index (URS-W3-020 AC-1).
	load_rows(start) {
		const row = this.current();
		if (!row || this.pending.has(`rows-${start}`)) {
			return;
		}
		this.busy(null, `rows-${start}`, true);
		this.$table.attr("aria-busy", "true");
		frappe
			.call("rheinwerk_mes.manufacturing_core.scheduling.board.board_rows", {
				schedule: row.name,
				start: start,
				page_length: this.page_length,
			})
			.then((response) => {
				const model = response.message;
				this.total = model.total;
				model.rows.forEach((entry, offset) => {
					this.rows[model.start + offset] = entry;
				});
				this.paint_rows();
			})
			.always(() => {
				this.busy(null, `rows-${start}`, false);
				if (!this.pending.size) {
					this.$table.removeAttr("aria-busy");
				}
			});
	}

	render_head() {
		const head = this.head;
		if (!head) {
			this.$head.empty();
			return;
		}
		const targets = (head.allowed_targets || []).length
			? head.allowed_targets.join(", ")
			: __("keine weiteren Übergänge");
		this.$head.html(`
			<div class="rw-board__headline">
				<span class="rw-mono">${this.esc(head.name)}</span>
				${this.state_pill(head)}
				<span>${__("Linie")}: <span class="rw-mono">${this.esc(head.production_line)}</span></span>
				<span>${__("Planbeginn")}: ${this.esc(head.planned_start)}</span>
				<span>${__("Aufträge")}: ${this.esc(head.total_entries)}</span>
				${
					head.decided_at
						? `<span>${__("Entschieden")}: ${this.esc(head.decided_at)} · ${this.esc(head.decided_by)}</span>`
						: ""
				}
				<span class="rw-board__targets">${__("Mögliche Übergänge")}: ${this.esc(targets)}</span>
			</div>
		`);
	}

	visible_range() {
		const height = this.$table.height() || 480;
		const scroll = this.$table.scrollTop() || 0;
		const first = Math.max(0, Math.floor(scroll / this.row_height) - 5);
		const count = Math.ceil(height / this.row_height) + 10;
		return [first, Math.min(this.total, first + count)];
	}

	paint_rows() {
		if (!this.total) {
			this.$table.html(`<p class="rw-board__empty">${__("Der Plan enthält keine Aufträge.")}</p>`);
			return;
		}
		const [first, last] = this.visible_range();
		let missing = null;
		const body = [];
		for (let index = first; index < last; index += 1) {
			const row = this.rows[index];
			if (!row) {
				if (missing === null) {
					missing = Math.floor(index / this.page_length) * this.page_length;
				}
				body.push(`<div class="rw-board__row is-placeholder" role="row" aria-hidden="true"></div>`);
				continue;
			}
			body.push(`
				<div class="rw-board__row" role="row" data-order="${this.esc(row.work_order)}"
					style="height:${this.row_height}px">
					<span role="cell" class="rw-num">${this.esc(row.sequence)}</span>
					<span role="cell" class="rw-mono">${this.esc(row.work_order)}</span>
					<span role="cell" class="rw-mono">${this.esc(row.production_item)}</span>
					<span role="cell" class="rw-num">${this.esc(row.quantity)}</span>
					<span role="cell">${this.esc(row.planned_start)}</span>
					<span role="cell">${this.esc(row.planned_end)}</span>
					<span role="cell" class="rw-num">${this.esc(row.realization)}</span>
					<span role="cell" class="rw-num">${this.esc(row.changeover)}</span>
					<span role="cell" class="rw-board__note">${this.esc(row.changeover_note)}</span>
				</div>`);
		}
		const header = `
			<div class="rw-board__row rw-board__row--head" role="row">
				<span role="columnheader">${__("Folge")}</span>
				<span role="columnheader">${__("Auftrag")}</span>
				<span role="columnheader">${__("Produkt")}</span>
				<span role="columnheader">${__("Menge")}</span>
				<span role="columnheader">${__("Start")}</span>
				<span role="columnheader">${__("Ende")}</span>
				<span role="columnheader">${__("Durchführung")}</span>
				<span role="columnheader">${__("Umrüstung")}</span>
				<span role="columnheader">${__("Hinweis")}</span>
			</div>`;
		this.$table.html(`
			${header}
			<div class="rw-board__spacer" style="height:${first * this.row_height}px"></div>
			${body.join("")}
			<div class="rw-board__spacer" style="height:${(this.total - last) * this.row_height}px"></div>
		`);
		if (missing !== null) {
			this.load_rows(missing);
		}
	}

	open_order(work_order) {
		const row = this.current();
		if (!row) {
			return;
		}
		frappe
			.call("rheinwerk_mes.manufacturing_core.scheduling.board.board_operations", {
				schedule: row.name,
				work_order: work_order,
			})
			.then((response) => {
				this.detail = { work_order: work_order, operations: response.message || [] };
				this.render_detail();
			});
	}

	render_detail() {
		if (!this.detail) {
			this.$detail.empty();
			return;
		}
		const rows = this.detail.operations
			.map(
				(row) => `
			<tr>
				<td class="rw-num">${this.esc(row.sequence)}</td>
				<td class="rw-mono">${this.esc(row.operation)}</td>
				<td class="rw-mono">${this.esc(row.workstation)}</td>
				<td class="rw-num">${this.esc(row.tpz)}</td>
				<td class="rw-num">${this.esc(row.tj)}</td>
				<td class="rw-num">${this.esc(row.duration)}</td>
				<td>${this.esc(row.planned_start)}</td>
				<td>${this.esc(row.planned_end)}</td>
			</tr>`
			)
			.join("");
		this.$detail.html(`
			<h4>${__("Arbeitsgänge")} · <span class="rw-mono">${this.esc(this.detail.work_order)}</span></h4>
			<table class="rw-board__ops">
				<thead>
					<tr>
						<th>${__("Folge")}</th>
						<th>${__("Arbeitsgang")}</th>
						<th>${__("Arbeitsplatz")}</th>
						<th>${__("Rüstzeit TPZ")}</th>
						<th>${__("Stückzeit TJ")}</th>
						<th>${__("Dauer")}</th>
						<th>${__("Start")}</th>
						<th>${__("Ende")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`);
	}

	decide($control, action) {
		const row = this.current();
		if (!row) {
			return;
		}
		const label = action === "approve" ? __("Plan freigeben") : __("Plan ablehnen");
		frappe.prompt(
			[
				{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Begründung"),
					reqd: action === "reject" ? 1 : 0,
				},
			],
			(values) => {
				this.busy($control, action, true);
				frappe
					.call(`rheinwerk_mes.manufacturing_core.scheduling.lifecycle.${action}`, {
						schedule: row.name,
						reason: values.reason,
					})
					.then(() => {
						frappe.show_alert({ message: label, indicator: "green" });
						this.load_schedules();
					})
					.always(() => this.busy($control, action, false));
			},
			label,
			label
		);
	}
};
