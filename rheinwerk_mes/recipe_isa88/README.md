# Recipe governance (W1-4) and ISA-88 batch recipes (Wave W2)

## Recipe governance — shipped in W1-4 (URS-W1-014 … URS-W1-017)

`gov_state` lifecycle over the governed anchor BOM/Routing pair (CDM-04, ADR-006):

- `doctype/recipe_governance/` — the `Recipe Governance` DocType and every enforcement rule
  (transition legality, role gate, validators, in-use lock, successor versioning)
- `validators.py` — the structural validator battery, a pure function over a recipe
  snapshot; re-implements Qcadoo `TechnologyValidationService.java:91-707`
- `governance.py` — snapshot builder, anchor `doc_event` change control and the read helpers
  `gov_state(recipe)` / `is_accepted(recipe)` other W1 children consume
- `bom_gov_state.js` — the `gov_state` pill on the anchor BOM form

Installer: `rheinwerk_mes/setup/w1_recipe_gov.py`. Design note:
`docs/design/W1-recipe-governance.md`.

## ISA-88 Batch Recipes — Rebuild (Wave W2)

White space in all three legacy systems. Net-new capability:

- Master and control recipes; procedure → unit procedure → operation → phase structure
- Process parameters (setpoints, ranges) per phase
- Formula scaling and recipe-to-work-order translation into the anchor layer
