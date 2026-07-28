"""Frappe app hooks for the consolidated Rheinwerk MES.

Layering (ARCHITECTURE.md): anchor ERPNext DocTypes are never forked — every
absorbed behaviour is registered here as a doc_event, workflow or custom field
owned by `rheinwerk_mes`.
"""

app_name = "rheinwerk_mes"
app_title = "Rheinwerk MES Core"
app_publisher = "Rheinwerk Chemie GmbH"
app_description = "Consolidated Manufacturing Execution System for centralised chemical operations"
app_email = "mes@rheinwerk-chemie.example"
app_license = "Proprietary"

required_apps = ["erpnext"]

# Fixtures exported with the app: custom fields, property setters, workflows and
# roles that extend anchor DocTypes without forking them.
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"module",
				"in",
				[
					"Manufacturing Core",
					"Execution Gating",
					"Genealogy",
					"Quality",
					"Warehouse",
					"Recipe ISA88",
					"Regulatory Hazmat",
					"Integration",
				],
			]
		],
	},
]

after_install = [
	"rheinwerk_mes.install.after_install",
	# W1-4: recipe governance (URS-W1-014 … URS-W1-017).
	"rheinwerk_mes.setup.w1_recipe_gov.setup_w1_recipe_gov",
	# W1-2/W1-3: execution gating + anchor hard-stop configuration (URS-W1-005 … URS-W1-013).
	"rheinwerk_mes.setup.w1_gating.setup_w1_gating",
	# W2-1/2/3: canonical Batch, `qa_state` workflow, genealogy tables (URS-W2-005/006).
	"rheinwerk_mes.setup.w2_genealogy.setup_w2_genealogy",
	# W2-4/W2-5: Quality Inspection extensions, disposition fields and the CoA
	# (URS-W2-013 … URS-W2-019).
	"rheinwerk_mes.setup.w2_quality.setup_w2_quality",
	# W2-7: hazmat / regulatory master data on Item and Batch (URS-W2-023/024).
	"rheinwerk_mes.setup.w2_hazmat.setup_w2_hazmat",
	# W1-8: role gating runs last so it can also stamp the governance workflow's
	# transitions (URS-W1-029).
	"rheinwerk_mes.setup.w1_roles.setup_w1_roles",
	# W2 fan-in: the business viewer's cross-module read surface (URS-W2-036 AC-2) — after
	# W1 roles, which creates the role, and after every W2 child installed its DocTypes.
	"rheinwerk_mes.setup.w2_rbac.setup_w2_rbac",
	# W3: the read-only permission surface of the e-signature evidence (DEC-W2-029).
	"rheinwerk_mes.setup.w3_esignature.setup_w3_esignature",
]

# Client-side additions to anchor forms; W1-4 renders the recipe's `gov_state` pill on the
# anchor BOM without forking it.
doctype_js = {
	"BOM": "recipe_isa88/bom_gov_state.js",
	# W2-7: the hazmat chip on the anchor Item and anchor Batch forms (URS-W2-024).
	"Item": "regulatory_hazmat/item_hazmat.js",
	"Batch": "regulatory_hazmat/batch_hazmat.js",
}

# W1-7: Desk/Terminal density tokens and status pills for the shop-floor screens.
# W2-1: the Trace Ribbon shares the shop-floor tokens and adds its own ribbon layout.
app_include_css = [
	"/assets/rheinwerk_mes/css/shopfloor.css",
	"/assets/rheinwerk_mes/css/trace_ribbon.css",
	# W2-4: the inspector's Work Queue → Detail screen.
	"/assets/rheinwerk_mes/css/inspection_queue.css",
	# W2-7: the hazmat chip's signal tone and icons (URS-W2-024).
	"/assets/rheinwerk_mes/css/hazmat.css",
]

# W2-7: one hazmat chip component shared by the Item/Batch forms, stock views and the
# Trace Ribbon (URS-W2-024).
app_include_js = [
	"/assets/rheinwerk_mes/js/hazmat.js",
	# W3: the German-first signing dialog for the four dispositive acts (DEC-W2-029).
	"/assets/rheinwerk_mes/js/esignature.js",
]

# W2-7: the Trace Ribbon page fetches its model from `genealogy.ribbon.ribbon`; the hazmat
# decoration is layered on through this additive override rather than by editing the
# genealogy package, so the ribbon shows Lagerklasse and UN number as chips (URS-W2-024)
# while `genealogy.ribbon.ribbon` itself stays the single producer of the trace model.
override_whitelisted_methods = {
	"rheinwerk_mes.genealogy.ribbon.ribbon": "rheinwerk_mes.regulatory_hazmat.views.ribbon",
}

doc_events = {
	# W0-2: item-level UoM conversion invariants (URS-W0-004).
	# W1: execution-gating hooks are appended here.
	"Item": {
		"validate": "rheinwerk_mes.manufacturing_core.uom.validate_uom_conversions",
		# W2-7: a changed item hazmat profile refreshes the derived batch mirrors
		# (URS-W2-024); the profile link stays the single source of truth.
		"on_update": "rheinwerk_mes.regulatory_hazmat.profiles.refresh_item_batches",
	},
	# W1-6: draft outbound Stock Entries make/release reservations (URS-W1-023/024).
	# W1-3: consuming a batch past its expiry is refused (URS-W1-013, policy URS-W1-030) —
	# the substrate skips its own expiry throw for Stock Entry vouchers.
	"Stock Entry": {
		"validate": [
			# Auto-allocation runs first so the expiry hard stop also sees the batches the
			# policy itself chose (URS-W1-030).
			"rheinwerk_mes.execution_gating.allocation.allocate_stock_entry_batches",
			"rheinwerk_mes.execution_gating.expiry.enforce_batch_expiry",
			# W2-3: a Blocked batch may not be consumed, and stock may not leave a
			# quarantine location without the QA/clerk role (URS-W2-011, URS-W2-012).
			"rheinwerk_mes.genealogy.blocking.enforce_blocked_batch_consumption",
			"rheinwerk_mes.genealogy.quarantine.enforce_quarantine_exit",
		],
		"on_update": "rheinwerk_mes.warehouse.reservations.on_stock_entry_update",
		"on_submit": [
			"rheinwerk_mes.warehouse.reservations.on_stock_entry_submit",
			# W2-1: genealogy links are written from the posting (URS-W2-001).
			"rheinwerk_mes.genealogy.links.on_stock_entry_submit",
		],
		"on_cancel": [
			"rheinwerk_mes.warehouse.reservations.on_stock_entry_cancel",
			"rheinwerk_mes.genealogy.links.on_stock_entry_cancel",
		],
		"on_trash": "rheinwerk_mes.warehouse.reservations.on_stock_entry_trash",
	},
	# W1-1: every `exec_state` change funnels through one validator (URS-W1-001…004).
	"Work Order": {
		"before_insert": "rheinwerk_mes.manufacturing_core.exec_state.set_default_exec_state",
		"validate": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
		"before_update_after_submit": "rheinwerk_mes.manufacturing_core.exec_state.validate_exec_state_change",
		# W1-2: post-transition side effects — reservations released on Declined/Abandoned
		# (URS-W1-009) and the executed transition logged immutably (URS-W1-033).
		"on_update": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
		"on_update_after_submit": "rheinwerk_mes.execution_gating.side_effects.on_work_order_update",
	},
	# W1-7: the job card's own name is the barcode the terminal scans (URS-W1-028).
	"Job Card": {
		"validate": "rheinwerk_mes.setup.w1_shopfloor.set_job_card_scan_code",
	},
	# W2-2/W2-3: every `qa_state` change funnels through one validator, and the executed
	# transition propagates blocked-ancestor advisories (URS-W2-006, URS-W2-009).
	"Batch": {
		# W2-7: the hazmat-mandatory gate refuses an unprofiled batch, and the read-only
		# UN-number/Lagerklasse mirrors are refreshed from the effective profile
		# (URS-W2-023 AC-2, URS-W2-024).
		"before_validate": [
			"rheinwerk_mes.regulatory_hazmat.profiles.enforce_hazmat_profile",
			"rheinwerk_mes.regulatory_hazmat.profiles.sync_batch_hazmat_fields",
		],
		"before_insert": "rheinwerk_mes.genealogy.qa_state.set_default_qa_state",
		"validate": "rheinwerk_mes.genealogy.qa_state.validate_qa_state_change",
		"on_update": "rheinwerk_mes.genealogy.blocking.on_batch_update",
	},
	# W2-4: an Accepted inspection releases its batch through the genealogy API
	# (URS-W2-014 AC-3).
	"Quality Inspection": {
		"on_submit": "rheinwerk_mes.quality.inspections.on_inspection_submit",
	},
	# W1-4: Accepted recipes are immutable and in-use recipes are locked
	# (URS-W1-016, URS-W1-017); changes need a new BOM version.
	# W3: the two remaining dispositive acts of DEC-W2-029 — issuing a certificate and
	# accepting a recipe — intercepted on their own documents.
	"CoA Certificate": {
		"before_insert": "rheinwerk_mes.compliance.gates.coa_issue_signature_gate",
	},
	"Recipe Governance": {
		"validate": "rheinwerk_mes.compliance.gates.recipe_accept_signature_gate",
	},
	"BOM": {
		"validate": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_update_after_submit": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
		"before_cancel": "rheinwerk_mes.recipe_isa88.governance.enforce_recipe_change_control",
	},
}

# W1-1: ordered gate callbacks run by
# `rheinwerk_mes.manufacturing_core.exec_state.transition` before a state change is
# written. Later waves append their gates here — no edit to the state machine needed.
# Each callable takes a `TransitionContext` and either appends German-first messages to
# `context.errors` / returns them, or throws its own modal.
rheinwerk_exec_state_gates = [
	"rheinwerk_mes.manufacturing_core.exec_state.reason_gate",
	"rheinwerk_mes.manufacturing_core.exec_state.anchor_submit_gate",
	"rheinwerk_mes.manufacturing_core.exec_state.shortfall_gate",
	# W1-2: execution gating (URS-W1-005 … URS-W1-008).
	"rheinwerk_mes.execution_gating.gates.acceptance_gate",
	"rheinwerk_mes.execution_gating.gates.recipe_accepted_gate",
	"rheinwerk_mes.execution_gating.gates.completion_gate",
	"rheinwerk_mes.execution_gating.gates.material_availability_gate",
	# W2-4: completion needs an Accepted Quality Inspection per produced batch
	# (URS-W2-014).
	"rheinwerk_mes.quality.gates.quality_inspection_gate",
]

# W2-2: ordered gate callbacks run by `rheinwerk_mes.genealogy.qa_state.transition` before
# a batch disposition is written. The W2-4 quality child appends its Quality-Inspection
# gate here — no edit to the state machine needed. Each callable takes a
# `qa_state.TransitionContext` (see `docs/design/W2-genealogy.md`).
rheinwerk_qa_state_gates = [
	"rheinwerk_mes.genealogy.qa_state.reason_gate",
	# W2-4: a Rejected inspection must be dispositioned before its batch can be released
	# (URS-W2-016).
	"rheinwerk_mes.quality.gates.rejected_inspection_gate",
	# W3: release and block are dispositive acts and need an electronic signature once
	# enforcement is switched on (DEC-W2-029 · URS-W2-029 AC-2). Registered last, so a
	# transition that fails a cheaper gate is refused before anyone is asked to sign.
	"rheinwerk_mes.compliance.gates.qa_state_signature_gate",
]
