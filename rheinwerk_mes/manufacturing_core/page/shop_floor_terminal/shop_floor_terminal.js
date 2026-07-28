// Shopfloor-Terminal — Terminal Card pattern (W1-7 · URS-W1-026…028, URS-W1-032, URS-W1-035).
//
// One task at a time, giant primary action, order/operation always in the header, an
// always-focused scan field, and a complete keyboard path (Enter/Esc/arrows, F2 density,
// ? shortcut sheet). Gated actions never show success before the server confirms.
// All user-facing strings go through __() — no concatenation (URS-W1-034).

frappe.pages["shop-floor-terminal"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Shopfloor-Terminal"),
		single_column: true,
	});
	new rheinwerk.ShopFloorTerminal(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.ShopFloorTerminal = class ShopFloorTerminal {
	constructor(page) {
		this.page = page;
		this.mode = "Terminal";
		this.state = { order: null, jobs: [], index: 0 };
		this.render_shell();
		this.bind_keyboard();
		this.set_mode(this.mode);
		this.focus_scan();
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-terminal" data-mode="Terminal">
				<header class="rw-terminal__header">
					<span class="rw-terminal__order rw-mono" data-ref="order">${__("Kein Auftrag")}</span>
					<span class="rw-terminal__operation" data-ref="operation">—</span>
					<span class="rw-pill" data-ref="pill"></span>
					<button class="rw-btn rw-btn--ghost" data-action="toggle-mode">${__("Dichtemodus (F2)")}</button>
				</header>
				<section class="rw-terminal__scan">
					<label for="rw-scan">${__("Scannen")}</label>
					<input id="rw-scan" class="rw-scan" autocomplete="off" data-ref="scan"
						placeholder="${__("Auftrag, Arbeitsgang oder Charge scannen")}" />
					<p class="rw-scan__error" data-ref="scan-error" role="alert" hidden></p>
				</section>
				<section class="rw-terminal__card" data-ref="card"></section>
				<section class="rw-terminal__queue" data-ref="queue" role="listbox"></section>
				<dialog class="rw-shortcuts" data-ref="shortcuts"></dialog>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$scan = this.$body.find('[data-ref="scan"]');
		this.$body.on("click", '[data-action="toggle-mode"]', () => this.toggle_mode());
		this.$body.on("click", "[data-job-action]", (event) =>
			this.run_job_action($(event.currentTarget).attr("data-job-action"), event.currentTarget)
		);
		this.$scan.on("change", () => this.handle_scan(this.$scan.val()));
		this.$scan.on("blur", () => setTimeout(() => this.focus_scan(), 0));
	}

	// Server-provided values (record names, operation labels, pill text) are escaped before
	// they reach innerHTML: a document name is user-controlled data, not markup.
	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	focus_scan() {
		this.$scan.trigger("focus");
	}

	bind_keyboard() {
		$(document).on("keydown.rw-terminal", (event) => {
			if (event.key === "F2") {
				event.preventDefault();
				this.toggle_mode();
			} else if (event.key === "?" ) {
				event.preventDefault();
				this.show_shortcuts();
			} else if (event.key === "Escape") {
				this.cancel();
			} else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
				event.preventDefault();
				this.move(event.key === "ArrowDown" ? 1 : -1);
			}
		});
	}

	cancel() {
		this.$body.find('[data-ref="shortcuts"]')[0]?.close();
		this.$body.find('[data-ref="scan-error"]').attr("hidden", true);
		this.$scan.val("");
		this.focus_scan();
	}

	toggle_mode() {
		this.set_mode(this.mode === "Terminal" ? "Desk" : "Terminal");
	}

	set_mode(mode) {
		// Terminal mode enlarges, it never hides: the same fields render in both modes.
		this.mode = mode;
		this.$body.attr("data-mode", mode);
		frappe.call({
			method: "rheinwerk_mes.manufacturing_core.shopfloor.ui.mode_profile",
			args: { mode },
			callback: (r) => {
				this.tokens = r.message;
			},
		});
	}

	show_shortcuts() {
		const rows = (this.tokens?.shortcuts || [])
			.map((s) => `<tr><td class="rw-mono">${this.esc(s.keys)}</td><td>${this.esc(s.action)}</td></tr>`)
			.join("");
		const dialog = this.$body.find('[data-ref="shortcuts"]');
		dialog.html(`<h3>${__("Tastaturkürzel")}</h3><table>${rows}</table>`);
		dialog[0].showModal();
	}

	beep() {
		// Audible scan confirmation; silent when the browser blocks autoplay.
		try {
			const context = new (window.AudioContext || window.webkitAudioContext)();
			const oscillator = context.createOscillator();
			oscillator.frequency.value = 880;
			oscillator.connect(context.destination);
			oscillator.start();
			setTimeout(() => oscillator.stop(), 80);
		} catch (error) {
			console.debug("scan confirmation tone unavailable", error);
		}
	}

	handle_scan(code) {
		if (!code) return;
		const $error = this.$body.find('[data-ref="scan-error"]');
		$error.attr("hidden", true);
		// UI feedback first (<100 ms), server confirmation before anything counts as done.
		this.$body.addClass("rw-terminal--pending");
		frappe
			.call({ method: "rheinwerk_mes.manufacturing_core.shopfloor.scanner.scan", args: { code } })
			.then((r) => {
				this.$body.removeClass("rw-terminal--pending");
				const result = r.message || {};
				this.$scan.val("");
				this.focus_scan();
				if (!result.recognised) {
					$error.text(result.message).removeAttr("hidden");
					return;
				}
				this.beep();
				this.highlight(result.highlight);
				if (result.kind === "work_order") {
					this.load_queue(result.name);
				}
			});
	}

	highlight(target) {
		this.$body.find("[data-highlight]").removeClass("rw-row--scanned");
		this.$body.find(`[data-highlight="${target}"]`).addClass("rw-row--scanned");
	}

	load_queue(work_order) {
		frappe
			.call({
				method: "rheinwerk_mes.manufacturing_core.shopfloor.job_execution.job_queue",
				args: { work_order },
			})
			.then((r) => {
				this.state.order = r.message;
				this.state.jobs = r.message.jobs || [];
				this.state.index = 0;
				this.render_queue();
			});
	}

	move(delta) {
		if (!this.state.jobs.length) return;
		const next = this.state.index + delta;
		this.state.index = Math.min(Math.max(next, 0), this.state.jobs.length - 1);
		this.render_queue();
	}

	render_queue() {
		const order = this.state.order;
		if (!order) return;
		this.$body.find('[data-ref="order"]').text(order.work_order);
		const job = this.state.jobs[this.state.index];
		this.$body.find('[data-ref="operation"]').text(job ? job.operation : "—");
		this.$body
			.find('[data-ref="pill"]')
			.attr("data-state", order.exec_state)
			.html(
				`<span class="rw-pill__icon" data-icon="${this.esc(order.exec_state_pill.icon)}"></span>` +
					`<span class="rw-pill__label">${this.esc(order.exec_state_pill.label)}</span>`
			);
		this.$body.find('[data-ref="card"]').html(job ? this.render_card(job) : "");
		this.$body.find('[data-ref="queue"]').html(
			this.state.jobs
				.map(
					(row, index) => `
					<div class="rw-row ${index === this.state.index ? "rw-row--current" : ""}"
						data-highlight="job_card:${this.esc(row.job_card)}" role="option">
						<span class="rw-mono">${this.esc(row.job_card)}</span>
						<span>${this.esc(row.operation)}</span>
						<span>${this.esc(row.workstation)}</span>
						<span class="rw-pill" data-state="${this.esc(row.job_status)}">
							<span class="rw-pill__icon" data-icon="${this.esc(row.status_pill.icon)}"></span>
							<span class="rw-pill__label">${this.esc(row.status_pill.label)}</span>
						</span>
						<span class="rw-num">${this.esc(row.total_completed_qty_display)}</span>
					</div>`
				)
				.join("")
		);
	}

	render_card(job) {
		const paused = job.is_paused;
		return `
			<div class="rw-card" data-highlight="job_card:${this.esc(job.job_card)}">
				<dl class="rw-card__facts">
					<dt>${__("Arbeitsgang")}</dt><dd>${this.esc(job.operation)}</dd>
					<dt>${__("Arbeitsplatz")}</dt><dd>${this.esc(job.workstation)}</dd>
					<dt>${__("Sollmenge")}</dt><dd class="rw-num">${this.esc(job.for_quantity_display)}</dd>
					<dt>${__("Erfasste Menge")}</dt><dd class="rw-num">${this.esc(job.total_completed_qty_display)}</dd>
				</dl>
				<div class="rw-card__actions">
					<button class="rw-btn rw-btn--primary" data-job-action="${paused ? "resume_job" : "start_job"}">
						${paused ? __("Arbeit fortsetzen") : __("Arbeit starten")}
					</button>
					<button class="rw-btn" data-job-action="pause_job" ${paused ? "disabled" : ""}>
						${__("Pausieren")}
					</button>
					<button class="rw-btn" data-job-action="record_output">${__("Menge erfassen")}</button>
				</div>
			</div>`;
	}

	run_job_action(action, control) {
		const job = this.state.jobs[this.state.index];
		if (!job) return;
		const args = { job_card: job.job_card };
		if (action === "record_output") {
			// Enter confirms the dialog, Esc cancels it — the same keyboard path as the card.
			frappe.prompt(
				{
					fieldname: "completed_qty",
					fieldtype: "Float",
					label: __("Erfasste Menge in kg"),
					default: job.for_quantity,
					reqd: 1,
				},
				(values) =>
					this.call_job_action(
						action,
						{ ...args, completed_qty: values.completed_qty, submit: 1 },
						control
					),
				__("Menge erfassen"),
				__("Buchen")
			);
			return;
		}
		this.call_job_action(action, args, control);
	}

	call_job_action(action, args, control) {
		// Progress lives on the control itself; success is only rendered after the server answers.
		$(control).addClass("rw-btn--busy").prop("disabled", true);
		frappe
			.call({
				method: `rheinwerk_mes.manufacturing_core.shopfloor.job_execution.${action}`,
				args,
			})
			.then((r) => {
				$(control).removeClass("rw-btn--busy").prop("disabled", false);
				if (!r.message) return;
				this.state.jobs[this.state.index] = r.message;
				this.render_queue();
				this.focus_scan();
			})
			.catch(() => $(control).removeClass("rw-btn--busy").prop("disabled", false));
	}
};
