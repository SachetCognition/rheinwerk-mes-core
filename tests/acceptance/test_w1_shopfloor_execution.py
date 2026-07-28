"""TC-W1-027 — operator job-card execution with time logs.

Verifies **URS-W1-026** (job cards per operation, time-log start/stop, completed-quantity
recording feeding the completion gate) through **TC-W1-027** of
`docs/test/TST-W1-production-core.md`.
"""

from __future__ import annotations

import pytest
from test_w1_shopfloor_support import FILL, MIX, as_operator, job_card, running_order

frappe = pytest.importorskip("frappe")
job_execution = pytest.importorskip("rheinwerk_mes.manufacturing_core.shopfloor.job_execution")


def test_job_queue_lists_the_order_operations(site):
	"""URS-W1-026 AC-1 / TC-W1-027 step 1 — MIX and FILL are listed against the order."""
	order = running_order(site)
	as_operator(site)
	queue = job_execution.job_queue(order.name)

	assert queue["work_order"] == order.name
	assert [job["operation"] for job in queue["jobs"]] == [MIX, FILL]
	assert {job["workstation"] for job in queue["jobs"]} == {"MIX-01", "FILL-01"}
	assert queue["exec_state_pill"]["icon"], "the queue header carries an icon-bearing pill"


def test_start_and_stop_write_a_time_log_with_duration(site):
	"""URS-W1-026 AC-2 / TC-W1-027 step 2 — start/stop stores start, end and duration."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)

	job_execution.start_job(card.name)
	view = job_execution.stop_job(card.name)

	logs = view["time_logs"]
	assert len(logs) == 1
	assert logs[0]["from_time"] and logs[0]["to_time"]
	assert logs[0]["time_in_mins"] >= 0
	assert view["job_status"] in ("Work In Progress", "Open")


def test_recording_output_submits_and_feeds_the_order(site):
	"""URS-W1-026 AC-3 / TC-W1-027 step 3 — 500 kg on FILL is the order's recorded output."""
	order = running_order(site)
	as_operator(site)
	# The anchor enforces the routing sequence: MIX is booked before FILL may be.
	mix = job_card(site, order, MIX)
	job_execution.start_job(mix.name)
	job_execution.record_output(mix.name, 500, submit=True)

	card = job_card(site, order, FILL)
	job_execution.start_job(card.name)
	view = job_execution.record_output(card.name, 500, submit=True)

	assert view["docstatus"] == 1
	assert view["total_completed_qty"] == 500
	assert view["total_completed_qty_display"] == "500,000 kg"

	output = job_execution.order_output(order.name)
	assert output["recorded_output"] == 500
	assert output["ordered_qty"] == 500


def test_execution_actions_are_refused_on_a_submitted_card(site):
	"""URS-W1-026 — a booked job card is closed for further execution actions."""
	order = running_order(site)
	card = job_card(site, order, MIX)
	as_operator(site)
	job_execution.start_job(card.name)
	job_execution.record_output(card.name, 500, submit=True)

	with pytest.raises(frappe.ValidationError):
		job_execution.start_job(card.name)


def test_anchor_job_card_is_not_forked(site):
	"""URS-W1-026 — the journey adopts the anchor Job Card; only Custom Fields are added."""
	assert site.db.get_value("DocType", "Job Card", "module") == "Manufacturing"
	assert (
		site.db.get_value("Custom Field", {"dt": "Job Card", "fieldname": "rw_scan_code"}, "module")
		== "Manufacturing Core"
	)
