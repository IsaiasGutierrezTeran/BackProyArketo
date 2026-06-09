"""Seed subscription plans (idempotent).

    python manage.py seed_plans
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.models import BillingInterval, SubscriptionPlan

PLANS = [
    ("free", "Free", "0.00", ["1 proyecto", "detección mock"]),
    ("pro", "Pro", "19.00", ["Proyectos ilimitados", "Mask R-CNN", "Riesgos IA"]),
    ("enterprise", "Enterprise", "99.00", ["Todo Pro", "Colaboración", "Soporte prioritario"]),
]


class Command(BaseCommand):
    help = "Crea los planes de suscripción (idempotente)."

    def handle(self, *args, **options):
        created = 0
        for code, name, price, features in PLANS:
            _, was_created = SubscriptionPlan.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "price": Decimal(price),
                    "interval": BillingInterval.MONTH, "features": features,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"seed_plans: {created} planes creados."))
