"""Parity contract definitions; importing this package registers every contract."""

from __future__ import annotations

from . import order_gating, technology, warehouse_picking  # noqa: F401

__all__ = ["order_gating", "technology", "warehouse_picking"]
