// Trace Ribbon — genealogy in one horizontal band (W2-1 · URS-W2-002, URS-W2-003).
//
// Suppliers left, the batch in focus centred, downstream products right. Status is always
// icon + label + colour (never colour alone); a blocked chip breaks its branch visibly.
// Keyboard: arrows move the selection, Enter recentres on the selected chip (expansion
// state survives), Esc closes the detail, Ctrl+P prints the same DOM the screen shows.
// Every string goes through __() (German-first, URS-W1-034); dates DD.MM.YYYY, mass kg.

frappe.pages["trace-ribbon"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Chargen-Trace"),
		single_column: true,
	});
	new rheinwerk.TraceRibbon(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.TraceRibbon = class TraceRibbon {
	constructor(page) {
		this.page = page;
		this.model = null;
		this.selected = 0;
		this.expanded = new Set();
		this.render_shell();
		this.bind_keyboard();
		const batch = frappe.utils.get_url_arg("batch") || frappe.get_route()[1];
		if (batch) {
			this.$batch.val(batch);
			this.load(batch);
		}
	}

	render_shell() {
		this.$body = $(`
			<div class="rw-ribbon">
				<header class="rw-ribbon__bar">
					<label for="rw-ribbon-batch">${__("Charge")}</label>
					<input id="rw-ribbon-batch" class="rw-mono" data-ref="batch" autocomplete="off"
						placeholder="${__("Chargennummer eingeben oder scannen")}" />
					<button class="rw-btn" data-action="load">${__("Spur anzeigen")}</button>
					<button class="rw-btn rw-btn--ghost" data-action="print">${__("Drucken")}</button>
					<span class="rw-ribbon__hint">${__("Pfeiltasten: Auswahl · Enter: neu zentrieren · Esc: Detail schließen")}</span>
				</header>
				<section class="rw-ribbon__band" data-ref="band" role="list" aria-label="${__("Chargen-Trace")}"></section>
				<aside class="rw-ribbon__detail" data-ref="detail" hidden></aside>
			</div>
		`);
		this.page.main.append(this.$body);
		this.$batch = this.$body.find('[data-ref="batch"]');
		this.$band = this.$body.find('[data-ref="band"]');
		this.$detail = this.$body.find('[data-ref="detail"]');
		this.$body.on("click", '[data-action="load"]', () => this.load(this.$batch.val()));
		this.$body.on("click", '[data-action="print"]', () => window.print());
		this.$body.on("click", "[data-chip]", (event) => {
			this.selected = Number($(event.currentTarget).attr("data-index"));
			this.render();
		});
		this.$body.on("dblclick", "[data-chip]", (event) =>
			this.load($(event.currentTarget).attr("data-chip"))
		);
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	}

	load(batch) {
		if (!batch) {
			return;
		}
		// The batch in focus stays expanded across recentres (URS-W2-003 AC-3).
		this.expanded.add(batch);
		frappe
			.call("rheinwerk_mes.genealogy.ribbon.ribbon", { batch })
			.then((response) => {
				this.model = response.message;
				this.selected = this.chips().findIndex((chip) => chip.side === "focus");
				this.$batch.val(batch);
				this.render();
			})
			.catch(() => frappe.msgprint(__("Charge {0} wurde nicht gefunden.", [batch])));
	}

	chips() {
		if (!this.model) {
			return [];
		}
		return [...this.model.left].reverse().concat([this.model.focus], this.model.right);
	}

	pill_html(pill) {
		return `<span class="rw-pill rw-pill--${this.esc(pill.tone)}">
			<span class="rw-pill__icon" data-icon="${this.esc(pill.icon)}" aria-hidden="true"></span>
			<span class="rw-pill__label">${this.esc(pill.label)}</span>
		</span>`;
	}

	chip_html(chip, index) {
		const qty = chip.qty == null ? "" : `${format_number(chip.qty, null, 3)} ${__("kg")}`;
		return `<article class="rw-chip" role="listitem" tabindex="-1"
				data-chip="${this.esc(chip.batch)}" data-index="${index}"
				data-side="${this.esc(chip.side)}"
				data-break="${chip.branch_break ? "1" : "0"}"
				aria-current="${index === this.selected ? "true" : "false"}">
			<h3 class="rw-chip__id rw-mono">${this.esc(chip.batch)}</h3>
			<p class="rw-chip__item">${this.esc(chip.item)}</p>
			<p class="rw-chip__qty">${this.esc(qty)}</p>
			<p class="rw-chip__expiry">${chip.expiry_date ? __("Verfall {0}", [this.esc(chip.expiry_date)]) : ""}</p>
			<div class="rw-chip__pills">${(chip.pills || []).map((pill) => this.pill_html(pill)).join("")}</div>
		</article>`;
	}

	render() {
		const chips = this.chips();
		if (!chips.length) {
			this.$band.html(`<p class="rw-ribbon__empty">${__("Keine Spur geladen.")}</p>`);
			return;
		}
		this.$band.html(chips.map((chip, index) => this.chip_html(chip, index)).join(""));
		this.render_detail(chips[this.selected]);
	}

	render_detail(chip) {
		if (!chip) {
			this.$detail.attr("hidden", true);
			return;
		}
		const rows = [
			[__("Charge"), chip.batch],
			[__("Artikel"), chip.item],
			[__("Qualitätszustand"), (chip.pills[0] || {}).label],
			[__("Verfallsdatum"), chip.expiry_date || __("—")],
			[__("Fertigungsauftrag"), chip.production_order || __("—")],
		];
		this.$detail
			.removeAttr("hidden")
			.html(
				`<dl>${rows
					.map(([term, value]) => `<dt>${this.esc(term)}</dt><dd>${this.esc(value)}</dd>`)
					.join("")}</dl>`
			);
	}

	bind_keyboard() {
		$(document).on("keydown.rw-ribbon", (event) => {
			if (frappe.get_route()[0] !== "trace-ribbon") {
				return;
			}
			const chips = this.chips();
			if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
				const step = event.key === "ArrowRight" ? 1 : -1;
				this.selected = Math.min(Math.max(this.selected + step, 0), chips.length - 1);
				this.render();
			} else if (event.key === "Enter" && chips[this.selected]) {
				this.load(chips[this.selected].batch);
			} else if (event.key === "Escape") {
				this.$detail.attr("hidden", true);
			}
		});
	}
};
