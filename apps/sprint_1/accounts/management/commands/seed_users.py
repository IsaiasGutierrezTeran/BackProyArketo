"""Seed a superadmin plus one demo user per role (idempotent).

Usage::

    python manage.py seed_users

Credentials are read from the environment when present, otherwise sensible dev
defaults are used (NEVER use these defaults in production).
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Role

User = get_user_model()

# (email, role, full_name, is_staff, is_superuser)
DEMO_USERS = [
    ("admin@arketo.dev", Role.SUPERADMIN, "Super Admin", True, True),
    ("cliente@arketo.dev", Role.CLIENTE, "Cliente Demo", False, False),
    (
        "arquitecto@arketo.dev",
        Role.ARQUITECTO,
        "Arquitecto Demo",
        False,
        False,
    ),
    ("ingeniero@arketo.dev", Role.INGENIERO, "Ingeniero Demo", False, False),
]


class Command(BaseCommand):
    help = "Crea un superadmin y un usuario demo por cada rol (idempotente)."

    def handle(self, *args, **options):
        admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "Admin12345")
        demo_password = os.environ.get("SEED_DEMO_PASSWORD", "Demo12345")

        created, skipped = 0, 0
        for email, role, full_name, is_staff, is_superuser in DEMO_USERS:
            if User.objects.filter(email=email).exists():
                skipped += 1
                continue
            password = admin_password if is_superuser else demo_password
            User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                is_staff=is_staff,
                is_superuser=is_superuser,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + {email} ({role})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_users: {created} creados, {skipped} ya existían."
            )
        )
