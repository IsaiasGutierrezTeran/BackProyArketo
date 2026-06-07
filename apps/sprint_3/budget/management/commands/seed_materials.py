"""Seed a materials catalog with Bolivian market prices (Bs), idempotent.

Precios de referencia del mercado boliviano (aprox., en bolivianos). Ajusta
`unit_price` según tu ciudad/fecha — están pensados como punto de partida realista.

    python manage.py seed_materials
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from budget.models import BlockQuality, Material, MaterialCategory

# categoría -> [(nombre, unidad, precio_Bs, calidad_bloque)]
CATALOG = {
    "Aglomerantes": [
        ("Cemento Portland IP-30 (bolsa 50 kg)", "bolsa", "58.00", BlockQuality.STANDARD),
        ("Cal hidratada (bolsa)", "bolsa", "28.00", BlockQuality.STANDARD),
        ("Yeso (bolsa 25 kg)", "bolsa", "30.00", BlockQuality.STANDARD),
    ],
    "Áridos": [
        ("Arena fina", "m³", "150.00", BlockQuality.STANDARD),
        ("Arena común", "m³", "130.00", BlockQuality.STANDARD),
        ("Grava / ripio", "m³", "190.00", BlockQuality.STANDARD),
        ("Piedra bruta", "m³", "160.00", BlockQuality.STANDARD),
    ],
    "Mampostería": [
        ("Ladrillo adobito", "unidad", "1.00", BlockQuality.LOW),
        ("Ladrillo gambote 6 huecos", "unidad", "2.20", BlockQuality.STANDARD),
        ("Ladrillo cerámico 18 huecos", "unidad", "4.50", BlockQuality.HIGH),
        ("Bloque de hormigón 15 cm", "unidad", "4.00", BlockQuality.STANDARD),
    ],
    "Aceros": [
        ("Fierro corrugado 1/2\" (varilla 12 m)", "varilla", "70.00", BlockQuality.STANDARD),
        ("Fierro corrugado 3/8\" (varilla 12 m)", "varilla", "42.00", BlockQuality.STANDARD),
        ("Malla electrosoldada", "m²", "28.00", BlockQuality.STANDARD),
        ("Alambre de amarre", "kg", "14.00", BlockQuality.STANDARD),
    ],
    "Acabados": [
        ("Pintura látex (balde 4 L)", "balde", "130.00", BlockQuality.STANDARD),
        ("Cerámica de piso (alta)", "m²", "75.00", BlockQuality.HIGH),
        ("Cerámica económica", "m²", "45.00", BlockQuality.STANDARD),
    ],
    "Cubierta": [
        ("Calamina galvanizada N°28 (plancha)", "plancha", "85.00", BlockQuality.STANDARD),
        ("Teja colonial", "unidad", "2.50", BlockQuality.STANDARD),
    ],
    "Instalaciones": [
        ("Tubería PVC 1/2\"", "m", "6.00", BlockQuality.STANDARD),
        ("Clavos", "kg", "14.00", BlockQuality.STANDARD),
    ],
}


class Command(BaseCommand):
    help = "Crea categorías y materiales con precios bolivianos (Bs), idempotente."

    def handle(self, *args, **options):
        created = 0
        for category_name, materials in CATALOG.items():
            category, _ = MaterialCategory.objects.get_or_create(name=category_name)
            for name, unit, price, quality in materials:
                _, was_created = Material.objects.get_or_create(
                    name=name,
                    defaults={
                        "category": category, "unit": unit,
                        "unit_price": Decimal(price), "block_quality": quality,
                    },
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"seed_materials: {created} materiales (precios Bs) creados."
        ))
