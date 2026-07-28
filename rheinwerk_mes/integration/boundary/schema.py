"""Versioned, machine-validated contract schemas (W3-3 · URS-W3-013).

The contract is committed as JSON Schema documents under
`rheinwerk_mes/integration/boundary/contract/<version>/<message-type>.schema.json` and
validated by the small, dependency-free validator in this module. A hand-rolled validator is
used deliberately: the offline CI job installs nothing but `pytest`, and the boundary must be
machine-validated in *every* job, including the one that runs without a site. The supported
keyword set is the one the contract uses — `type`, `required`, `properties`,
`additionalProperties`, `enum`, `const`, `pattern`, `minimum`, `exclusiveMinimum`,
`minLength`, `minItems`, `items`, `format: date` / `date-time`.

Version discipline (URS-W3-013 AC-2):

* `versions()` lists every committed contract version; `CONTRACT_VERSION` (1.0) is the frozen
  one and every message carries its version in the payload, so two versions can be served
  simultaneously during a transition window;
* `requires_version_increment(old, new)` decides whether a proposed schema change is
  backward-incompatible (a new required property, a narrowed enum, a removed property, a
  changed type or a newly forbidden extra property) and therefore needs a new version
  directory rather than an edit of the frozen one.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from rheinwerk_mes.integration.boundary import contracts

CONTRACT_ROOT = Path(__file__).resolve().parent / "contract"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

SCHEMA_FILENAMES: dict[str, str] = {
	contracts.ORDERS_IN: "orders-in.schema.json",
	contracts.CONFIRMATION_OUT: "confirmation-out.schema.json",
	contracts.GL_POSTING_OUT: "gl-posting-out.schema.json",
}


class SchemaViolation(contracts.BoundaryError):
	"""A payload does not satisfy its contract schema (reason code CONTRACT_VIOLATION)."""

	def __init__(self, message: str, path: str) -> None:
		super().__init__(contracts.REASON_CONTRACT_VIOLATION, message, path=path)


def versions() -> tuple[str, ...]:
	"""Committed contract versions, oldest first (directory `v1.0` is version `1.0`)."""
	return tuple(sorted(child.name.removeprefix("v") for child in CONTRACT_ROOT.iterdir() if child.is_dir()))


def version_directory(version: str) -> Path:
	"""The committed directory of one contract version."""
	return CONTRACT_ROOT / f"v{version}"


@cache
def schema(message_type: str, version: str = contracts.CONTRACT_VERSION) -> dict[str, Any]:
	"""The committed schema of one message type at one contract version."""
	if message_type not in SCHEMA_FILENAMES:
		raise ValueError(f"unknown message type: {message_type}")
	path = version_directory(version) / SCHEMA_FILENAMES[message_type]
	if not path.exists():
		raise ValueError(f"contract version {version} has no schema for {message_type}")
	return json.loads(path.read_text(encoding="utf-8"))


def validate_message(payload: dict[str, Any]) -> dict[str, Any]:
	"""Validate a boundary message against the schema its own header names.

	The header (`message_type`, `contract_version`) is checked first so that an unroutable
	message fails with the same machine-readable reason code as a malformed body.
	"""
	if not isinstance(payload, dict):
		raise SchemaViolation("Nachricht ist kein Objekt", "$")
	message_type = payload.get("message_type")
	if message_type not in contracts.MESSAGE_TYPES:
		raise SchemaViolation(f"Unbekannter Nachrichtentyp: {message_type!r}", "$.message_type")
	version = payload.get("contract_version")
	if version not in versions():
		raise SchemaViolation(f"Unbekannte Vertragsversion: {version!r}", "$.contract_version")
	validate(payload, schema(message_type, version))
	return payload


def validate(payload: Any, definition: dict[str, Any], path: str = "$") -> None:
	"""Validate `payload` against `definition`; raises `SchemaViolation` on the first error."""
	expected = definition.get("type")
	if expected and not _type_matches(payload, expected):
		raise SchemaViolation(f"Erwarteter Typ {expected}, erhalten {_type_name(payload)}", path)

	if "const" in definition and payload != definition["const"]:
		raise SchemaViolation(f"Wert muss {definition['const']!r} sein", path)
	if "enum" in definition and payload not in definition["enum"]:
		raise SchemaViolation(f"Wert {payload!r} nicht in {definition['enum']}", path)

	if isinstance(payload, str):
		_validate_string(payload, definition, path)
	elif isinstance(payload, bool):
		pass
	elif isinstance(payload, (int, float)):
		_validate_number(payload, definition, path)
	elif isinstance(payload, list):
		_validate_array(payload, definition, path)
	elif isinstance(payload, dict):
		_validate_object(payload, definition, path)


def _validate_string(payload: str, definition: dict[str, Any], path: str) -> None:
	pattern = definition.get("pattern")
	if pattern and not re.fullmatch(pattern, payload):
		raise SchemaViolation(f"Wert {payload!r} entspricht nicht dem Muster {pattern}", path)
	if "minLength" in definition and len(payload) < definition["minLength"]:
		raise SchemaViolation(f"Wert kürzer als {definition['minLength']} Zeichen", path)
	fmt = definition.get("format")
	if fmt == "date":
		_parse(payload, "%Y-%m-%d", path, "JJJJ-MM-TT")
	elif fmt == "date-time":
		try:
			datetime.fromisoformat(payload)
		except ValueError as exc:
			raise SchemaViolation(f"Kein ISO-8601-Zeitstempel: {payload!r}", path) from exc


def _parse(value: str, fmt: str, path: str, human: str) -> date:
	try:
		return datetime.strptime(value, fmt).date()
	except ValueError as exc:
		raise SchemaViolation(f"Kein Datum im Format {human}: {value!r}", path) from exc


def _validate_number(payload: float, definition: dict[str, Any], path: str) -> None:
	if "minimum" in definition and payload < definition["minimum"]:
		raise SchemaViolation(f"Wert {payload} unter Minimum {definition['minimum']}", path)
	if "exclusiveMinimum" in definition and payload <= definition["exclusiveMinimum"]:
		raise SchemaViolation(f"Wert {payload} muss größer als {definition['exclusiveMinimum']} sein", path)


def _validate_array(payload: list[Any], definition: dict[str, Any], path: str) -> None:
	if "minItems" in definition and len(payload) < definition["minItems"]:
		raise SchemaViolation(f"Weniger als {definition['minItems']} Einträge", path)
	item_definition = definition.get("items")
	if item_definition:
		for index, item in enumerate(payload):
			validate(item, item_definition, f"{path}[{index}]")


def _validate_object(payload: dict[str, Any], definition: dict[str, Any], path: str) -> None:
	properties: dict[str, Any] = definition.get("properties", {})
	for field in definition.get("required", []):
		if payload.get(field) is None:
			raise SchemaViolation(f"Pflichtfeld fehlt: {field}", f"{path}.{field}")
	if definition.get("additionalProperties") is False:
		for field in payload:
			if field not in properties:
				raise SchemaViolation(f"Unbekanntes Feld: {field}", f"{path}.{field}")
	for field, sub_definition in properties.items():
		if field in payload and payload[field] is not None:
			validate(payload[field], sub_definition, f"{path}.{field}")


_TYPES: dict[str, tuple[type, ...]] = {
	"object": (dict,),
	"array": (list,),
	"string": (str,),
	"boolean": (bool,),
	"number": (int, float),
	"integer": (int,),
	"null": (type(None),),
}


def _type_matches(payload: Any, expected: str | list[str]) -> bool:
	names = [expected] if isinstance(expected, str) else list(expected)
	for name in names:
		allowed = _TYPES.get(name)
		if not allowed:
			raise ValueError(f"unsupported schema type: {name}")
		if name in ("number", "integer") and isinstance(payload, bool):
			continue
		if isinstance(payload, allowed):
			return True
	return False


def _type_name(payload: Any) -> str:
	for name, types in _TYPES.items():
		if name != "number" and isinstance(payload, types):
			return name
	return type(payload).__name__


def requires_version_increment(old: dict[str, Any], new: dict[str, Any]) -> bool:
	"""True when the change from `old` to `new` is not backward-compatible.

	A consumer written against `old` must keep working against `new`; anything that can
	break such a consumer (or reject a message it used to send) forces a new contract
	version instead of an edit of the frozen one (URS-W3-013 AC-2).
	"""
	return bool(_incompatibilities(old, new, "$"))


def incompatibilities(old: dict[str, Any], new: dict[str, Any]) -> tuple[str, ...]:
	"""Human-readable list of the backward-incompatible differences (empty when safe)."""
	return _incompatibilities(old, new, "$")


def _incompatibilities(old: dict[str, Any], new: dict[str, Any], path: str) -> tuple[str, ...]:
	found: list[str] = []
	if old.get("type") != new.get("type"):
		found.append(f"{path}: Typ geändert ({old.get('type')} → {new.get('type')})")

	old_required = set(old.get("required", []))
	new_required = set(new.get("required", []))
	for field in sorted(new_required - old_required):
		found.append(f"{path}.{field}: neues Pflichtfeld")

	old_properties: dict[str, Any] = old.get("properties", {})
	new_properties: dict[str, Any] = new.get("properties", {})
	for field in sorted(set(old_properties) - set(new_properties)):
		found.append(f"{path}.{field}: Feld entfernt")
	if new.get("additionalProperties") is False and old.get("additionalProperties") is not False:
		found.append(f"{path}: zusätzliche Felder nun verboten")

	for field, old_definition in old_properties.items():
		new_definition = new_properties.get(field)
		if not isinstance(new_definition, dict) or not isinstance(old_definition, dict):
			continue
		old_enum, new_enum = old_definition.get("enum"), new_definition.get("enum")
		if old_enum and new_enum and set(new_enum) < set(old_enum):
			found.append(f"{path}.{field}: Wertebereich eingeschränkt")
		found.extend(_incompatibilities(old_definition, new_definition, f"{path}.{field}"))
	return tuple(found)


def fixture(name: str) -> dict[str, Any]:
	"""Load one committed contract fixture by file name (never inline them in tests)."""
	path = FIXTURE_ROOT / name
	if not path.exists():
		raise ValueError(f"unknown contract fixture: {name}")
	return json.loads(path.read_text(encoding="utf-8"))


def fixture_names() -> tuple[str, ...]:
	"""Every committed contract fixture, sorted."""
	return tuple(sorted(path.name for path in FIXTURE_ROOT.glob("*.json")))
