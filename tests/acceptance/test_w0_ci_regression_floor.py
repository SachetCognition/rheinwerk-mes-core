"""TC-W0-003 — CI gates lint and test failures (URS-W0-002).

The pipeline itself is the deliverable, so these checks pin its contract: a lint job
and a test job that both run on every pull request, against a pinned toolchain that
developers can reproduce locally. A pipeline definition that stops gating lint or
tests — the failure mode AC-1/AC-2 guard against — fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEV_REQUIREMENTS = REPO_ROOT / "requirements-dev.txt"


@pytest.fixture(scope="module")
def workflow() -> dict:
	return yaml.safe_load(WORKFLOW.read_text())


def _job_commands(workflow: dict, job: str) -> str:
	steps = workflow["jobs"][job]["steps"]
	return "\n".join(step["run"] for step in steps if "run" in step)


def test_ci_workflow_runs_on_pull_requests(workflow: dict) -> None:
	# PyYAML resolves the unquoted `on` key to the boolean True (YAML 1.1).
	triggers = workflow.get("on", workflow.get(True))
	assert "pull_request" in triggers


def test_lint_job_gates_ruff_check_and_format(workflow: dict) -> None:
	commands = _job_commands(workflow, "lint")
	assert "ruff check" in commands
	assert "ruff format --check" in commands


def test_test_job_runs_the_suites(workflow: dict) -> None:
	commands = _job_commands(workflow, "tests")
	assert "pytest tests" in commands
	# AC-2: the short summary names each failing test in the job log.
	assert "-rf" in commands


def test_toolchain_is_pinned_and_shared_by_both_jobs(workflow: dict) -> None:
	requirements = DEV_REQUIREMENTS.read_text()
	assert "ruff==" in requirements
	assert "pytest==" in requirements
	for job in ("lint", "tests"):
		assert "pip install -r requirements-dev.txt" in _job_commands(workflow, job)


def test_lint_and_test_configuration_live_in_pyproject() -> None:
	pyproject = (REPO_ROOT / "pyproject.toml").read_text()
	assert "[tool.ruff.lint]" in pyproject
	assert "[tool.pytest.ini_options]" in pyproject
