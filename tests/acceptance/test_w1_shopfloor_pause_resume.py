"""TC-W1-028 — pause/resume with time-log split.

Verifies **URS-W1-027** (On Hold semantics on job cards, logs split accordingly, submission
refused while On Hold) through **TC-W1-028** of `docs/test/TST-W1-production-core.md`.
Anchor behaviour adopted: `job_card.py:1371-1397` (pause/resume) and `:912-959`
(submission refused while On Hold).
"""

from __future__ import annotations

import pytest
from test_w1_shopfloor_support import MIX, as_operator, job_card, running_order

frappe = pytest.importorskip("frappe")
job_execution = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.job_execution")


def test_pause_closes_the_open_log_and_holds_the_card(site):
	"""URS-W1-027 AC-1 / TC-W1-028 step 1 — On Hold; the running time log is closed."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)
	job_execution.start_job(card.name)

	view = job_execution.pause_job(card.name)

	assert view["is_paused"] == 1
	assert view["job_status"] == "On Hold"
	assert view["time_logs"][-1]["to_time"], "the open log is closed on pause"


def test_resume_opens_a_new_log_and_returns_to_work_in_progress(site):
	"""URS-W1-027 AC-1 / TC-W1-028 step 2 — a new time log; Work In Progress again."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)
	job_execution.start_job(card.name)
	job_execution.pause_job(card.name)

	view = job_execution.resume_job(card.name)

	assert view["is_paused"] == 0
	assert view["job_status"] == "Work In Progress"
	assert len(view["time_logs"]) == 2
	assert not view["time_logs"][-1]["to_time"], "the resumed log is still running"


def test_submission_is_refused_while_the_card_is_on_hold(site):
	"""URS-W1-027 AC-2 / TC-W1-028 step 3 — a paused card cannot be booked."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)
	job_execution.start_job(card.name)
	job_execution.pause_job(card.name)

	with pytest.raises(frappe.ValidationError) as refusal:
		job_execution.record_output(card.name, 500, submit=True)

	assert "On Hold" in str(refusal.value) or "pausiert" in str(refusal.value)
	assert site.db.get_value("Job Card", card.name, "docstatus") == 0


def test_resume_is_refused_when_the_card_is_not_paused(site):
	"""URS-W1-027 — resume only applies to an On Hold card, in the plant's voice."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)
	job_execution.start_job(card.name)

	with pytest.raises(frappe.ValidationError):
		job_execution.resume_job(card.name)
