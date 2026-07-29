"""Idempotent site setup owned by `rheinwerk_mes`.

Everything the app needs on top of the unmodified ERPNext substrate is created
from code here — Custom Fields, Property Setters, workflows and roles — so that a
clean `bench install-app rheinwerk_mes` produces the same site as a migrated one.
Nothing is ever created by hand on a site.

Entry points: `after_install` (see `rheinwerk_mes.install`) and the `patches.txt`
entries.
"""
