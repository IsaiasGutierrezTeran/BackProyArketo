"""Seed a large, realistic Bolivian construction materials catalog (~1000 SKUs).

Prices are in **bolivianos (Bs)** and are realistic market reference points
(approx.); adjust by city/date if needed. The catalog is generated procedurally
by combining base products with variant dimensions (brand, size, grade), so it
covers the real breadth of a hardware/ferretería + corralón. Idempotent: only
inserts names that don't already exist.

    python manage.py seed_materials
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from budget.models import BlockQuality, Material, MaterialCategory

STD = BlockQuality.STANDARD
HIGH = BlockQuality.HIGH
LOW = BlockQuality.LOW


def _build_catalog() -> list[tuple]:
    """Return a list of (category, name, unit, price_bs, quality)."""
    out: list[tuple] = []

    def add(cat, name, unit, price, q=STD):
        out.append((cat, name[:120], unit, round(float(price), 2), q))

    # ---------------------------------------------------------------- Aglomerantes
    cem_brands = [
        "Soboce",
        "Viacha",
        "Fancesa",
        "Coboce",
        "Itacamba",
        "Yura",
        "El Puente",
        "Emisa",
        "Camba",
        "Warnes",
    ]
    for i, b in enumerate(cem_brands):
        add(
            "Aglomerantes",
            f"Cemento Portland IP-30 {b} (bolsa 50 kg)",
            "bolsa",
            56 + i,
        )
        add(
            "Aglomerantes",
            f"Cemento Portland IP-40 {b} (bolsa 50 kg)",
            "bolsa",
            62 + i,
            HIGH,
        )
        add(
            "Aglomerantes",
            f"Cemento Portland {b} (bolsa 25 kg)",
            "bolsa",
            32 + i * 0.5,
        )
    for i, c in enumerate(["hidratada", "viva", "agrícola"]):
        add("Aglomerantes", f"Cal {c} (bolsa 25 kg)", "bolsa", 26 + i * 4)
    for i, y in enumerate(
        ["estándar", "rápido", "fino para enlucir", "Paris"]
    ):
        add("Aglomerantes", f"Yeso {y} (bolsa 25 kg)", "bolsa", 28 + i * 3)
    for i, p in enumerate(
        [
            "interior",
            "exterior",
            "porcelanato",
            "alta adherencia",
            "piscinas",
            "piedra",
        ]
    ):
        add(
            "Aglomerantes",
            f"Pegamento cerámico {p} (bolsa 25 kg)",
            "bolsa",
            45 + i * 6,
            HIGH if i >= 3 else STD,
        )
    for i, a in enumerate(
        [
            "acelerante",
            "plastificante",
            "impermeabilizante",
            "desencofrante",
            "fragüe",
            "expansor",
        ]
    ):
        add(
            "Aglomerantes",
            f"Aditivo para hormigón {a} (4 L)",
            "balde",
            70 + i * 12,
        )

    # --------------------------------------------------------------------- Áridos
    for i, s in enumerate(["fina", "común", "gruesa", "lavada", "de río"]):
        add("Áridos", f"Arena {s} (m³)", "m³", 120 + i * 12)
        add("Áridos", f"Arena {s} (volqueta 6 m³)", "volqueta", 700 + i * 70)
    for i, g in enumerate(
        [
            'Grava 3/4"',
            'Grava 1/2"',
            "Ripio común",
            "Gravilla",
            "Piedra bruta",
            "Piedra manzana",
            "Confitillo",
        ]
    ):
        add("Áridos", f"{g} (m³)", "m³", 150 + i * 14)
    for i, g in enumerate(['Grava 3/4"', "Ripio común", "Piedra bruta"]):
        add("Áridos", f"{g} (volqueta 6 m³)", "volqueta", 900 + i * 80)

    # --------------------------------------------------------------------- Aceros
    rebar = [
        ('1/4"', 6, 16),
        ('3/8"', 8, 42),
        ('1/2"', 12, 70),
        ('5/8"', 16, 112),
        ('3/4"', 20, 168),
        ('7/8"', 22, 205),
        ('1"', 25, 268),
    ]
    for d, mm, price in rebar:
        add(
            "Aceros",
            f"Fierro corrugado {d} ({mm} mm) varilla 12 m",
            "varilla",
            price,
        )
        add(
            "Aceros",
            f"Fierro corrugado {d} ({mm} mm) varilla 9 m",
            "varilla",
            round(price * 0.76, 2),
        )
    for i, m in enumerate(
        ["15x15 cm Ø4.2", "15x15 cm Ø6", "10x10 cm Ø6", "20x20 cm Ø8"]
    ):
        add(
            "Aceros",
            f"Malla electrosoldada {m} (panel 6x2.4 m)",
            "panel",
            150 + i * 35,
        )
    for i, c in enumerate(
        ["recocido N°16", "recocido N°18", "galvanizado", "de púas (rollo)"]
    ):
        add("Aceros", f"Alambre {c}", "kg", 12 + i * 2)
    for i, n in enumerate(
        ['1"', '1 1/2"', '2"', '2 1/2"', '3"', '4"', "de calamina", "de acero"]
    ):
        add("Aceros", f"Clavo {n}", "kg", 13 + i)
    profiles = [
        "Tubo cuadrado 20x20",
        "Tubo cuadrado 30x30",
        "Tubo cuadrado 40x40",
        "Tubo rectangular 40x20",
        'Ángulo 1"',
        'Ángulo 1 1/2"',
        'Platina 1"',
        "Perfil C 80",
        "Perfil C 100",
        'Tubo redondo 1"',
    ]
    for i, p in enumerate(profiles):
        add("Aceros", f"{p} (barra 6 m)", "barra", 55 + i * 9)

    # --------------------------------------------------------------- Mampostería
    brick = [
        ("Adobito", 0.9, LOW),
        ("Gambote 6 huecos", 2.2, STD),
        ("Gambote 18 huecos", 3.8, STD),
        ("Cerámico 18 huecos", 4.5, HIGH),
        ("Cerámico 21 huecos", 5.2, HIGH),
        ("Hueco 8 huecos", 3.2, STD),
        ("Refractario", 7.5, HIGH),
        ("Visto / king kong", 6.0, HIGH),
    ]
    for name, price, q in brick:
        for j, b in enumerate(["Incerpaz", "Cerabol", "Faboce", "nacional"]):
            add(
                "Mampostería",
                f"Ladrillo {name} ({b})",
                "unidad",
                price + j * 0.2,
                q,
            )
    for i, b in enumerate(
        ["10 cm", "12 cm", "15 cm", "20 cm", "decorativo", "vibrado 15 cm"]
    ):
        add(
            "Mampostería",
            f"Bloque de hormigón {b}",
            "unidad",
            3.2 + i * 0.7,
            HIGH if i >= 4 else STD,
        )

    # ------------------------------------------------------------------- Cubierta
    for i, n in enumerate(["N°26", "N°28", "N°30", "N°32"]):
        for j, t in enumerate(
            ["galvanizada", "trapezoidal", "ondulada", "prepintada"]
        ):
            add(
                "Cubierta",
                f"Calamina {t} {n} (plancha 3.6 m)",
                "plancha",
                70 + i * 8 + j * 10,
                HIGH if j == 3 else STD,
            )
    for i, t in enumerate(
        ["colonial", "española", "plana", "francesa", "de hormigón"]
    ):
        add("Cubierta", f"Teja {t}", "unidad", 2.3 + i * 0.6)
    for i, p in enumerate(
        [
            "alveolar 6 mm",
            "alveolar 8 mm",
            "alveolar 10 mm",
            "compacto 3 mm",
            "ondulado",
        ]
    ):
        add(
            "Cubierta",
            f"Policarbonato {p} (plancha 2.10x5.80 m)",
            "plancha",
            380 + i * 60,
            HIGH,
        )
    for i, f in enumerate(["ondulada 6 mm", "ondulada 8 mm", "plana"]):
        add(
            "Cubierta", f"Plancha de fibrocemento {f}", "plancha", 120 + i * 25
        )
    for i, c in enumerate(
        [
            "caballete galvanizado",
            "cumbrera de teja",
            "canaleta PVC",
            "bajante PVC",
        ]
    ):
        add("Cubierta", f"{c.capitalize()}", "unidad", 35 + i * 12)

    # ------------------------------------------------------------------- Acabados
    cer_designs = [
        "Madera",
        "Mármol",
        "Cemento",
        "Hidráulico",
        "Travertino",
        "Liso blanco",
        "Gris urbano",
        "Beige",
        "Pizarra",
        "Granito",
        "Rústico",
        "Decorado",
        "Hexagonal",
        "Subway",
        "Terrazo",
    ]
    sizes = [("30x30", 0.85), ("45x45", 1.0), ("60x60", 1.35), ("20x60", 1.2)]
    for d in cer_designs:
        for sz, f in sizes:
            add(
                "Acabados",
                f"Cerámica {d} {sz} cm (m²)",
                "m²",
                round(40 * f + 6, 2),
            )
            add(
                "Acabados",
                f"Porcelanato {d} {sz} cm (m²)",
                "m²",
                round(85 * f + 10, 2),
                HIGH,
            )
    paint_types = [
        ("Látex interior", 120, STD),
        ("Látex exterior", 150, STD),
        ("Esmalte sintético", 95, STD),
        ("Anticorrosivo", 110, STD),
        ("Óleo mate", 130, STD),
        ("Impermeabilizante", 180, HIGH),
        ("Barniz marino", 140, HIGH),
    ]
    paint_sizes = [("1 L", 0.28), ("4 L", 1.0), ("18 L", 4.2)]
    paint_brands = ["Monopol", "Imperquim", "Sherwin", "Coral", "Tekno"]
    for tname, base, q in paint_types:
        for sz, f in paint_sizes:
            for b in paint_brands[:3]:
                add(
                    "Acabados",
                    f"{tname} {b} ({sz})",
                    "balde",
                    round(base * f, 2),
                    q,
                )
    for i, a in enumerate(
        [
            "blanco 20x30",
            "decorado 20x30",
            "rústico 25x40",
            "brillante 30x45",
            "mate 30x60",
        ]
    ):
        add("Acabados", f"Azulejo {a} cm (m²)", "m²", 38 + i * 9)
    for i, m in enumerate(
        [
            "masilla plástica",
            "empaste interior",
            "empaste exterior",
            "sellador acrílico",
            "silicona neutra",
            "fragua porcelana",
            "fragua estándar",
            "estuco",
            "microcemento",
            "venecitas (m²)",
        ]
    ):
        add("Acabados", f"{m.capitalize()}", "unidad", 22 + i * 7)
    for i, c in enumerate(
        [
            "placa de yeso 8 mm",
            "placa de yeso 12 mm",
            "cielo raso PVC (m²)",
            "molde de cornisa",
            "perfil de cielo raso 3 m",
        ]
    ):
        add("Acabados", f"{c.capitalize()}", "unidad", 28 + i * 12)

    # --------------------------------------------------------- Instalaciones (agua)
    diam = ['1/2"', '3/4"', '1"', '1 1/4"', '1 1/2"', '2"', '3"', '4"']
    for i, d in enumerate(diam):
        add(
            "Instalaciones",
            f"Tubería PVC presión {d} (6 m)",
            "tira",
            18 + i * 9,
        )
        add(
            "Instalaciones",
            f"Tubería PVC desagüe {d} (6 m)",
            "tira",
            22 + i * 11,
        )
        add(
            "Instalaciones",
            f"Tubería CPVC agua caliente {d} (3 m)",
            "tira",
            26 + i * 10,
            HIGH,
        )
        add(
            "Instalaciones",
            f"Tubería PPR termofusión {d} (4 m)",
            "tira",
            30 + i * 12,
            HIGH,
        )
    fittings = [
        "Codo 90°",
        "Codo 45°",
        "Tee",
        "Unión",
        "Reducción",
        "Tapón",
        "Cupla",
        "Niple",
        "Adaptador",
        "Llave de paso",
    ]
    for i, f in enumerate(fittings):
        for d in diam[:6]:
            add(
                "Instalaciones",
                f"{f} PVC {d}",
                "unidad",
                round(2.5 + i * 0.8 + diam.index(d) * 1.2, 2),
            )
    for i, s in enumerate(
        [
            ("Inodoro de tanque bajo", 480, STD),
            ("Inodoro one-piece", 950, HIGH),
            ("Lavamanos con pedestal", 320, STD),
            ("Lavamanos de sobreponer", 420, HIGH),
            ("Grifería de lavamanos", 180, STD),
            ("Grifería monomando", 360, HIGH),
            ("Ducha eléctrica", 220, STD),
            ("Mezcladora de ducha", 290, STD),
            ("Sifón de PVC", 35, STD),
            ("Rejilla de piso", 25, STD),
        ]
    ):
        name, price, q = s
        add("Instalaciones", name, "unidad", price, q)

    # ----------------------------------------------------------- Eléctrico
    for i, c in enumerate(["14 AWG", "12 AWG", "10 AWG", "8 AWG", "6 AWG"]):
        add("Eléctrico", f"Cable THW {c} (rollo 100 m)", "rollo", 180 + i * 90)
        add("Eléctrico", f"Cable concéntrico {c} (m)", "m", 4 + i * 2)
    elec = [
        ("Tomacorriente doble", 18),
        ("Interruptor simple", 14),
        ("Interruptor doble", 20),
        ("Interruptor conmutador", 22),
        ("Breaker 1P 16A", 28),
        ("Breaker 1P 20A", 30),
        ("Breaker 2P 32A", 65),
        ("Tablero 6 polos", 110),
        ("Tablero 12 polos", 180),
        ("Foco LED 9 W", 12),
        ("Foco LED 15 W", 18),
        ("Panel LED 18 W", 45),
        ("Caja octogonal", 4),
        ("Caja rectangular", 4),
        ("Cinta aislante", 8),
        ("Canaleta PVC 20x10 (2 m)", 14),
        ('Tubo corrugado 3/4" (rollo)', 60),
    ]
    for name, price in elec:
        add("Eléctrico", name, "unidad", price)

    # --------------------------------------------------------------------- Madera
    for i, t in enumerate(
        [
            'Tabla de encofrado 1"',
            'Listón 2x2"',
            'Listón 2x3"',
            'Viga 4x4"',
            "Machimbre (m²)",
            "Terciado 18 mm",
            "MDF 15 mm",
            "OSB 11 mm",
        ]
    ):
        add("Madera", f"{t}", "unidad", 35 + i * 18)
    for i, p in enumerate(
        [
            ("Puerta placa lisa", 320, STD),
            ("Puerta tablero", 620, HIGH),
            ("Puerta de cedro", 980, HIGH),
            ("Puerta metálica", 750, STD),
            ("Marco de puerta", 180, STD),
            ("Marco de ventana", 160, STD),
        ]
    ):
        name, price, q = p
        for sz in ["0.70 m", "0.80 m", "0.90 m"]:
            add(
                "Madera",
                f"{name} {sz}",
                "unidad",
                price + ["0.70 m", "0.80 m", "0.90 m"].index(sz) * 20,
                q,
            )

    # ------------------------------------------------------------------ Aberturas
    for i, m in enumerate(
        [
            "aluminio corredera",
            "aluminio proyectante",
            "PVC corredera",
            "PVC oscilobatiente",
        ]
    ):
        for sz in ["1.0x1.0 m", "1.2x1.2 m", "1.5x1.2 m", "2.0x1.5 m"]:
            add(
                "Aberturas",
                f"Ventana {m} {sz}",
                "unidad",
                round(
                    450
                    + i * 120
                    + [
                        "1.0x1.0 m",
                        "1.2x1.2 m",
                        "1.5x1.2 m",
                        "2.0x1.5 m",
                    ].index(sz)
                    * 90,
                    2,
                ),
                HIGH if "PVC" in m else STD,
            )
    for i, e in enumerate(
        ["4 mm", "6 mm", "8 mm", "templado 6 mm", "laminado", "espejo"]
    ):
        add(
            "Aberturas",
            f"Vidrio {e} (m²)",
            "m²",
            60 + i * 25,
            HIGH if i >= 3 else STD,
        )

    # ---------------------------------------------------------------------- Pisos
    for i, p in enumerate(
        [
            "Piso flotante 8 mm",
            "Piso flotante 12 mm",
            "Piso vinílico SPC",
            "Parquet de madera",
            "Piso laminado AC4",
        ]
    ):
        for q2 in ["clase económica", "clase premium"]:
            add(
                "Pisos",
                f"{p} ({q2}) (m²)",
                "m²",
                round(70 + i * 18 + (60 if "premium" in q2 else 0), 2),
                HIGH if "premium" in q2 else STD,
            )
    for i, z in enumerate(
        [
            "Zócalo de madera",
            "Zócalo de PVC",
            "Zócalo cerámico",
            "Perfil de transición",
            "Manta acústica (m²)",
        ]
    ):
        add("Pisos", f"{z}", "m", 12 + i * 6)

    # ------------------------------------------------------- Herramientas / varios
    tools = [
        ("Carretilla buggy", 380),
        ("Pala punta", 65),
        ("Pala cuadrada", 65),
        ("Picota", 80),
        ("Plancha de albañil", 55),
        ("Frotacho", 35),
        ("Nivel de 60 cm", 70),
        ("Flexómetro 5 m", 30),
        ("Plomada", 25),
        ("Balde de construcción", 18),
        ("Carretilla de obra", 420),
        ('Disco de corte 7"', 14),
        ('Broca para concreto 1/2"', 22),
        ("Guantes de obra (par)", 12),
        ("Casco de seguridad", 45),
        ("Cinta métrica 30 m", 60),
        ("Manguera de nivel (m)", 3),
        ("Lija para pared (pliego)", 4),
        ('Brocha 3"', 16),
        ('Rodillo 9"', 28),
    ]
    for name, price in tools:
        add("Herramientas", name, "unidad", price)

    return out


class Command(BaseCommand):
    help = "Crea ~1000 materiales de construcción con precios bolivianos (Bs), idempotente."

    def handle(self, *args, **options):
        catalog = _build_catalog()

        cat_names = {row[0] for row in catalog}
        cats = {
            n: MaterialCategory.objects.get_or_create(name=n)[0]
            for n in cat_names
        }

        existing = set(Material.objects.values_list("name", flat=True))
        to_create = []
        seen = set()
        for category, name, unit, price, quality in catalog:
            if name in existing or name in seen:
                continue
            seen.add(name)
            to_create.append(
                Material(
                    category=cats[category],
                    name=name,
                    unit=unit,
                    unit_price=Decimal(str(price)),
                    block_quality=quality,
                )
            )

        Material.objects.bulk_create(to_create, batch_size=500)
        total = Material.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"seed_materials: {len(to_create)} nuevos (precios Bs) · "
                f"{len(catalog)} en catálogo · {total} materiales en total."
            )
        )
