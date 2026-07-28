// Planungswarteschlange — W3-1 Production Plan / MRP journey (URS-W3-001, URS-W3-004).
//
// Desk-density read view of the firm Production Plans and the Work Orders generated from
// them. Every order shows the one status pill used across the MES (icon + label + colour),
// mass in kg and dates as DD.MM.YYYY. All strings go through __() — no concatenation.

frappe.pages["planning-queue"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Planungswarteschlange"),
		single_column: true,
	});
	new rheinwerk.PlanningQueue(page);
};

window.rheinwerk = window.rheinwerk || {};

rheinwerk.PlanningQueue = class PlanningQueue {
	constructor(page) {
		this.page = page;
		this.$body = $('<div class="rw-planning-queue"></div>').appendTo(page.main);
		this.page.set_primary_action(__("Aktualisieren"), () => this.refresh(), "refresh");
		this.refresh();
	}

	refresh() {
		frappe.call({
			method: "rheinwerk_mes.manufacturing_core.planning.view.get_planning_queue",
			callback: (r) => this.render(r.message || { plans: [], orders: [] }),
		});
	}

	render(model) {
		this.$body.empty();
		this.$body.append(this.render_plans(model.plans));
		this.$body.append(this.render_orders(model.orders));
	}

	render_plans(plans) {
		const $section = $(`<section class="rw-pq-section"><h3>${__("Produktionspläne")}</h3></section>`);
		if (!plans.length) {
			$section.append(`<p class="text-muted">${__("Keine freigegebenen Pläne")}</p>`);
			return $section;
		}
		const $table = $(`
			<table class="table table-bordered rw-pq-table">
				<thead><tr>
					<th>${__("Plan")}</th>
					<th>${__("Fertigungslinie")}</th>
					<th>${__("Datum")}</th>
					<th>${__("Aufträge")}</th>
				</tr></thead>
				<tbody></tbody>
			</table>`);
		const $tbody = $table.find("tbody");
		plans.forEach((p) => {
			$tbody.append(`
				<tr>
					<td class="rw-mono">${frappe.utils.escape_html(p.name)}</td>
					<td>${frappe.utils.escape_html(p.production_line || "—")}</td>
					<td>${frappe.utils.escape_html(p.posting_date_display || "")}</td>
					<td>${frappe.utils.escape_html(String(p.order_count))}</td>
				</tr>`);
		});
		$section.append($table);
		return $section;
	}

	render_orders(orders) {
		const $section = $(`<section class="rw-pq-section"><h3>${__("Fertigungsaufträge")}</h3></section>`);
		if (!orders.length) {
			$section.append(`<p class="text-muted">${__("Keine Aufträge erzeugt")}</p>`);
			return $section;
		}
		const $table = $(`
			<table class="table table-bordered rw-pq-table">
				<thead><tr>
					<th>${__("Auftrag")}</th>
					<th>${__("Artikel")}</th>
					<th>${__("Menge")}</th>
					<th>${__("Linie")}</th>
					<th>${__("Start")}</th>
					<th>${__("Status")}</th>
				</tr></thead>
				<tbody></tbody>
			</table>`);
		const $tbody = $table.find("tbody");
		orders.forEach((o) => {
			const $row = $(`
				<tr>
					<td class="rw-mono">${frappe.utils.escape_html(o.name)}</td>
					<td>${frappe.utils.escape_html(o.item_name || o.production_item)}</td>
					<td class="rw-num">${frappe.utils.escape_html(o.qty_display)}</td>
					<td>${frappe.utils.escape_html(o.production_line || "—")}</td>
					<td>${frappe.utils.escape_html(o.planned_start_display || "")}</td>
					<td></td>
				</tr>`);
			$row.find("td").last().append(this.pill(o.pill));
			$tbody.append($row);
		});
		$section.append($table);
		return $section;
	}

	pill(pill) {
		return $(
			`<span class="rw-pill" data-state="${frappe.utils.escape_html(pill.state)}">` +
				`<span class="rw-pill__icon">${frappe.utils.escape_html(pill.icon)}</span>` +
				`<span class="rw-pill__label">${frappe.utils.escape_html(pill.label)}</span>` +
				`</span>`
		);
	}
};
