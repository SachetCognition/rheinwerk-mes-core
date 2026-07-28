"""Parity contract definitions; importing this package registers every contract."""

from __future__ import annotations

from . import expiry, genealogy, order_gating, technology, warehouse_picking  # noqa: F401

__all__ = ["expiry", "genealogy", "order_gating", "technology", "warehouse_picking"]
