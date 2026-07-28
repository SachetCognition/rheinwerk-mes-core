"""W2 migration pilot — open batches, genealogy history and legacy quality flags.

Site-backed acceptance suite for URS-W2-030…032 (`docs/urs/URS-W2-traceability-quality.md`
§3.10), mapped from `docs/test/TST-W2-traceability-quality.md`:

* TC-W2-042 — matched-pair dual-model merge (URS-W2-030).
* TC-W2-043 — orphan resource strings + a rehearsed batch-load rollback (URS-W2-030).
* TC-W2-044 — genealogy history load, trace boundary and genealogy-only rollback (URS-W2-031).
* TC-W2-045 — legacy quality flags as qa_state history only, zero synthetic inspections (URS-W2-032).

The pilot data lives in committed extracts under
`rheinwerk_mes/integration/migration/fixtures/w2/` (never inlined here). Every test runs on
the `site` fixture, whose writes roll back per test, so the loaders are called directly
(they do not commit) and isolation is preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

from rheinwerk_mes.integration.migration.w2 import extract as w2_extract  # noqa: E402
from rheinwerk_mes.integration.migration.w2 import model as w2_model  # noqa: E402

MIG = "rheinwerk_mes.integration.migration"
W2 = f"{MIG}.w2"
GEN = "rheinwerk_mes.genealogy"


def load_plant(site, extract) -> dict[str, str]:
	"""Run all three load steps for a plant, returning the per-step run ids."""
	batches = site.get_attr(f"{W2}.loaders.load_batches")(extract)
	links = site.get_attr(f"{W2}.loaders.load_links")(extract)
	state = site.get_attr(f"{W2}.loaders.load_state")(extract)
	return {"batches": batches.run_id, "links": links.run_id, "state": state.run_id}


def failing(plant) -> list[str]:
	return [
		f"{c.key}: Quelle={c.source} Ziel={c.target} ({c.detail})" for c in plant.checks if c.status != "PASS"
	]


# --------------------------------------------------------------------------------------
# TC-W2-042 — matched-pair merge (URS-W2-030)
# --------------------------------------------------------------------------------------


def test_tc_w2_042_matched_pair_merges_into_one_canonical_batch(site):
	"""TC-W2-042 (URS-W2-030 AC-1/AC-3): the Qcadoo genealogy Batch GB-100 and its resource
	strings GB-100 (two lots, expiries 30.06.2026 / 31.07.2026) merge into ONE canonical
	Batch carrying both legacy refs, genealogy_incomplete=False, the earliest expiry, and a
	reported expiry conflict; counts, qa_state distribution, the 100-record spot-check and
	the (batch_id, item, expiry_date) checksum all reconcile PASS."""
	extract = w2_extract.extract_qcadoo()
	load_plant(site, extract)

	assert site.db.exists("Batch", "GB-100")
	batch = site.get_doc("Batch", "GB-100")
	assert batch.item == "RW-CHM-0001"
	assert str(batch.expiry_date) == "2026-06-30"  # earliest of the two lots wins
	assert not batch.genealogy_incomplete
	assert batch.qa_state == w2_model.RELEASED  # BatchState TRACKED → Released

	refs = {(row.source_entity, row.source_identifier) for row in batch.legacy_refs}
	assert ("advancedgenealogy_batch", "GB-100") in refs
	assert ("materialflowresources_resource", "GB-100") in refs

	assert any("GB-100" in conflict for conflict in extract.expiry_conflicts)

	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert plant.status == "PASS", failing(plant)
	keyed = {c.key: c for c in plant.checks}
	assert keyed["batch_count"].status == "PASS"
	assert keyed["identity_checksum"].status == "PASS"
	assert keyed["identity_spot_check"].status == "PASS"
	assert keyed["qa_state_distribution"].status == "PASS"


# --------------------------------------------------------------------------------------
# TC-W2-043 — orphan resource strings + rehearsed rollback (URS-W2-030)
# --------------------------------------------------------------------------------------


def test_tc_w2_043_orphan_string_is_identity_only_and_flagged_incomplete(site):
	"""TC-W2-043 (URS-W2-030 AC-2): the resource string RB-ORPHAN with no genealogy Batch
	becomes an identity-only canonical Batch flagged genealogy_incomplete, keeping only its
	resource legacy ref."""
	extract = w2_extract.extract_qcadoo()
	load_plant(site, extract)

	assert site.db.exists("Batch", "RB-ORPHAN")
	orphan = site.get_doc("Batch", "RB-ORPHAN")
	assert orphan.genealogy_incomplete
	refs = {(row.source_entity, row.source_identifier) for row in orphan.legacy_refs}
	assert refs == {("materialflowresources_resource", "RB-ORPHAN")}


def test_tc_w2_043_batch_load_rollback_by_run_id_then_clean_rerun(site):
	"""TC-W2-043 (URS-W2-030 rollback condition): a batch-count divergence rolls the batch
	load back by run id — deleting exactly that run's batches — and a clean re-run reconciles
	PASS again. The run journal is what the rollback replays (rollback logging)."""
	extract = w2_extract.extract_qcadoo()
	result = site.get_attr(f"{W2}.loaders.load_batches")(extract)
	assert site.db.exists("Batch", "GB-100")

	# Inject a count divergence: a batch the load created disappears.
	site.delete_doc("Batch", "RB-ORPHAN", force=True, delete_permanently=True)
	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert plant.status == "FAIL"
	assert {c.key for c in plant.checks if c.status == "FAIL"} & {"batch_count", "identity_checksum"}

	# The journal persisted the run; rolling it back removes exactly this run's batches.
	journal = site.get_attr(f"{MIG}.importer.read_journal")(result.run_id)
	assert [entry.name for entry in journal.journal]
	outcome = site.get_attr(f"{W2}.rollback.rollback_run")(result.run_id)
	assert outcome["deleted"] >= 1
	assert not site.db.exists("Batch", "GB-100")
	assert not site.db.exists("Batch", "GB-400")

	# A clean re-run reconciles PASS (identity spot-check + checksum + counts).
	load_plant(site, extract)
	rerun = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert rerun.status == "PASS", failing(rerun)


# --------------------------------------------------------------------------------------
# TC-W2-044 — genealogy history load + trace boundary (URS-W2-031)
# --------------------------------------------------------------------------------------


def test_tc_w2_044_consumed_links_preserve_used_rows_one_to_one(site):
	"""TC-W2-044 (URS-W2-031 AC-1): the Qcadoo TrackingRecord used tree lands as consumed
	genealogy links with quantities preserved one-to-one; link counts by direction, the
	zero-orphan check and the backward-trace spot-check all reconcile PASS."""
	extract = w2_extract.extract_qcadoo()
	load_plant(site, extract)

	consumed = {
		row["batch"]: row["qty"] for row in site.get_attr(f"{GEN}.links.links_of")("GB-300", "consumed")
	}
	assert consumed == {"GB-100": 80.0, "GB-200": 20.0}

	tree = site.get_attr(f"{GEN}.trace.backward")("GB-300")
	nodes = {node["batch"] for node in site.get_attr(f"{GEN}.trace.flatten")(tree)}
	assert nodes == {"GB-300", "GB-100", "GB-200"}

	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	keyed = {c.key: c for c in plant.checks}
	assert keyed["consumed_links"].status == "PASS"
	assert keyed["produced_links"].status == "PASS"
	assert keyed["orphan_links"].status == "PASS"
	assert keyed["backward_trace"].status == "PASS"


def test_tc_w2_044_plant_b_missing_lotid_sets_trace_boundary(site):
	"""TC-W2-044 (URS-W2-031 AC-2): a Plant B produced batch whose consumed input has no
	lotId is flagged genealogy_incomplete with the plant-wide OFBiz trace-boundary date, while
	a fully-traced produced batch is complete."""
	extract = w2_extract.extract_ofbiz()
	load_plant(site, extract)

	incomplete = site.get_doc("Batch", "LOT-B-901")
	assert incomplete.genealogy_incomplete
	assert str(incomplete.trace_boundary_date) == "2025-01-01"

	complete = site.get_doc("Batch", "LOT-B-900")
	assert not complete.genealogy_incomplete

	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert plant.status == "PASS", failing(plant)
	assert {c.key: c for c in plant.checks}["trace_boundary"].status == "PASS"


def test_tc_w2_044_genealogy_only_rollback_retains_batches(site):
	"""TC-W2-044 (URS-W2-031 rollback condition): a dangling (orphan) link makes
	reconciliation FAIL; rolling back the genealogy-link step alone by run id removes the
	links while the batches URS-W2-030 created are retained."""
	extract = w2_extract.extract_qcadoo()
	site.get_attr(f"{W2}.loaders.load_batches")(extract)
	links_run = site.get_attr(f"{W2}.loaders.load_links")(extract)
	assert site.get_attr(f"{GEN}.links.links_of")("GB-300", "consumed")

	# Turn a loaded consumed link into an orphan by removing its target leaf batch, so a
	# genealogy link now points at a batch that no longer exists.
	site.delete_doc("Batch", "GB-200", force=True, delete_permanently=True)
	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert {c.key: c for c in plant.checks}["orphan_links"].status == "FAIL"

	site.get_attr(f"{W2}.rollback.rollback_run")(links_run.run_id)

	# Links gone …
	assert site.get_attr(f"{GEN}.links.links_of")("GB-300", "consumed") == []
	# … but the batches URS-W2-030 created are retained (retention semantics).
	assert site.db.exists("Batch", "GB-300")
	assert site.db.exists("Batch", "GB-100")
	clean = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	assert {c.key: c for c in clean.checks}["orphan_links"].status == "PASS"


# --------------------------------------------------------------------------------------
# TC-W2-045 — quality flags as state history only (URS-W2-032)
# --------------------------------------------------------------------------------------


def test_tc_w2_045_blocked_for_qc_becomes_quarantined_with_history(site):
	"""TC-W2-045 (URS-W2-032 AC-1): a resource flagged blockedForQualityControl migrates to
	qa_state Quarantined with a qa_state_history row naming the legacy flag as the origin —
	and BatchState BLOCKED migrates to Blocked with its own origin note."""
	extract = w2_extract.extract_qcadoo()
	load_plant(site, extract)

	quarantined = site.get_doc("Batch", "GB-400")
	assert quarantined.qa_state == w2_model.QUARANTINED
	history = site.get_attr(f"{GEN}.qa_state.state_history")("GB-400")
	assert history and any("blockedForQualityControl" in (row["reason"] or "") for row in history)

	blocked = site.get_doc("Batch", "GB-200")
	assert blocked.qa_state == w2_model.BLOCKED
	blocked_history = site.get_attr(f"{GEN}.qa_state.state_history")("GB-200")
	assert any("BLOCKED" in (row["reason"] or "") for row in blocked_history)


def test_tc_w2_045_no_synthetic_quality_inspection_and_distributions_reconcile(site):
	"""TC-W2-045 (URS-W2-032 AC-2): the migration creates no Quality Inspection record (none
	predates the cut date) and the Quarantined/Blocked counts reconcile against the legacy
	flags. The local qa_state vocabulary must equal the genealogy module's."""
	# Resolved via the site (not a top-level import) so this module imports offline.
	assert (w2_model.QUARANTINED, w2_model.RELEASED, w2_model.BLOCKED) == (
		site.get_attr(f"{GEN}.qa_state.QUARANTINED"),
		site.get_attr(f"{GEN}.qa_state.RELEASED"),
		site.get_attr(f"{GEN}.qa_state.BLOCKED"),
	)

	qi_before = site.db.count("Quality Inspection")
	extract = w2_extract.extract_qcadoo()
	load_plant(site, extract)
	assert site.db.count("Quality Inspection") == qi_before  # zero synthetic inspections

	qi_check = site.get_attr(f"{W2}.reconcile.quality_inspection_check")()
	assert qi_check.status == "PASS", qi_check.detail

	plant = site.get_attr(f"{W2}.reconcile.reconcile_plant")(extract)
	keyed = {c.key: c for c in plant.checks}
	assert keyed["flagged_counts"].status == "PASS", keyed["flagged_counts"]
	assert keyed["qa_state_distribution"].status == "PASS", keyed["qa_state_distribution"]
