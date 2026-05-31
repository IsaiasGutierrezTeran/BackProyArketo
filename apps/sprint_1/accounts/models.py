"""User model with role-based access for Arketo.

JWT authentication works identically for web (Angular) and mobile (Flutter):
both send ``Authorization: Bearer <access>``.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class Role(models.TextChoices):
    """Application roles mapped to the use cases."""

    SUPERADMIN = "superadmin", "Superadministrador"
    CLIENTE = "cliente", "Cliente"
    ARQUITECTO = "arquitecto", "Arquitecto"
    INGENIERO = "ingeniero", "Ingeniero"


class User(AbstractBaseUser, PermissionsMixin):
    """Email-authenticated user."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENTE)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # Reflects the active plan code; the source of truth is the billing app (Sprint 3).
    subscription_plan = models.CharField(max_length=30, default="free")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # email + password only

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email

    # --- Role convenience flags (used by permissions/serializers) -----------
    @property
    def is_superadmin(self) -> bool:
        return self.role == Role.SUPERADMIN or self.is_superuser

    @property
    def is_ingeniero(self) -> bool:
        return self.role == Role.INGENIERO

    @property
    def is_arquitecto(self) -> bool:
        return self.role == Role.ARQUITECTO
