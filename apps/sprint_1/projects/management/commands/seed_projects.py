"""Seed a few demo projects for the demo users (idempotent).

Run after `seed_users`::

    python manage.py seed_projects
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from projects.models import Project, ProjectStatus

User = get_user_model()

# (owner_email, name, description, status)
DEMO_PROJECTS = [
    ("cliente@arketo.dev", "Casa habitación 120m²", "Vivienda unifamiliar de una planta.", ProjectStatus.ACTIVE),
    ("cliente@arketo.dev", "Local comercial", "Remodelación de local en planta baja.", ProjectStatus.DRAFT),
    ("arquitecto@arketo.dev", "Edificio de oficinas", "Anteproyecto de 3 niveles.", ProjectStatus.ACTIVE),
]


class Command(BaseCommand):
    help = "Crea proyectos demo para los usuarios sembrados (idempotente)."

    def handle(self, *args, **options):
        created, skipped = 0, 0
        for owner_email, name, description, status in DEMO_PROJECTS:
            owner = User.objects.filter(email=owner_email).first()
            if owner is None:
                self.stdout.write(
                    self.style.WARNING(f"  ! usuario {owner_email} no existe; corre seed_users primero.")
                )
                continue
            if Project.objects.filter(owner=owner, name=name).exists():
                skipped += 1
                continue
            Project.objects.create(owner=owner, name=name, description=description, status=status)
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + {name} ({owner_email})"))

        self.stdout.write(
            self.style.SUCCESS(f"seed_projects: {created} creados, {skipped} ya existían.")
        )
