"""Seed subscription plans (idempotent).

    python manage.py seed_plans
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.models import BillingInterval, SubscriptionPlan

# Precios en BOLIVIANOS (Bs). Las features describen lo que habilita cada plan
# (enforzado en core.entitlements).
PLANS = [
    ("free", "Free", "0.00", ["1 proyecto", "Detección mock"]),
    ("pro", "Pro", "19.00", ["Proyectos ilimitados", "Mask R-CNN / IA visión", "Riesgos IA", "Colaboración"]),
    ("enterprise", "Enterprise", "99.00", ["Todo Pro", "Soporte prioritario"]),
]


class Command(BaseCommand):
    help = "Crea/actualiza los planes de suscripción en Bs (idempotente)."

    def handle(self, *args, **options):
        for code, name, price, features in PLANS:
            # update_or_create para que re-seedear ajuste precio/nombre/features
            # de planes existentes (p. ej. al pasar a bolivianos).
            SubscriptionPlan.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "price": Decimal(price),
                    "interval": BillingInterval.MONTH, "features": features,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"seed_plans: {len(PLANS)} planes sincronizados (Bs)."))
