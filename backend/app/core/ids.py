"""
Small identifier helpers shared by the service and controller layers.

This lives in ``app/core`` rather than a controller module so services can use it
without importing the ``app.controllers`` package (which would create an import
cycle: controllers -> services -> controllers).
"""
from __future__ import annotations

import uuid


def parse_uuid_or_derive(raw_id: str | None) -> uuid.UUID:
    """Parses a UUID string or deterministically derives a valid UUID from it."""
    if not raw_id:
        from db.models import generate_uuid

        return generate_uuid()
    try:
        return uuid.UUID(raw_id)
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_id))
