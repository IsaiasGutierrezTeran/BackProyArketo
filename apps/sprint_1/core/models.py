"""Shared abstract models."""

from __future__ import annotations

from django.db import models


class BaseModel(models.Model):
    """Abstract base with a primary key and audit timestamps.

    Every concrete model in the system inherits from this so that ``id``,
    ``created_at`` and ``updated_at`` are uniform across apps.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
