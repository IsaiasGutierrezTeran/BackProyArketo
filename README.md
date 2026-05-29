# Arketo — Backend (Django REST Framework)

Backend de **Arketo**: *Plataforma de Inteligencia Espacial para la Coordinación
de Obras, Control Presupuestario y Digitalización de Planos 2D→3D*. Consumido por
web (Angular), móvil (Flutter) y un módulo de IA.

> Estado: **Sprints 1–3 entregados** — los 18 casos de uso. Apps: core · accounts ·
> projects (+colaboración) · plans · detection · modeling · ai_design · risk · budget ·
> sketch_2d · versioning · billing.

Las apps se agrupan en disco por sprint en `apps/sprint_N/` (trazabilidad código ↔
documentación). Cada app se importa por su nombre corto (`core`, `accounts`,
`plans`, …); ver `config/settings/base.py` (añade cada `apps/sprint_N/` al `sys.path`).

## Arquitectura

- **Package by feature**: una app Django por módulo de negocio.
- **Capa de servicios**: la lógica vive en `services.py`; las views solo orquestan
  (validar → llamar servicio → responder). Serializers solo I/O; validadores en `validators.py`.
- **`core`** transversal: `BaseModel`, envelope estándar, paginación, excepciones, permisos, utilidades.
- **Envelope estándar** en toda respuesta:
  - Éxito: `{ "success": true, "data": <payload>, "meta": { ... } }`
  - Error: `{ "success": false, "error": { "code": <str>, "detail": <str|obj> } }`
  - En listados, la paginación va en `meta.pagination`.
- **URLs de archivos absolutas** (`core.utils.absolute_media_url`) para que el móvil pueda consumirlas.
- Código en inglés; mensajes de usuario en español.

## Apps · Casos de uso · Sprint

| App | Sprint | Casos de uso |
|-----|--------|--------------|
| `core` | 1 | Transversal (envelope, paginación, permisos, BaseModel) |
| `accounts` | 1 | Acceso (registro/login/logout/refresh), usuarios (CRUD superadmin), perfil, roles |
| `projects` | 1 | Project (raíz) + dashboard y sincronización (HU-16); colaboración/comentarios (HU-14) |
| `plans` | 2 | Subir/validar plano (HU-4) |
| `detection` | 2 | IA: Mask R-CNN (vía floorplan-api) + GLB con trimesh; interfaz Detector + Mock (HU-5) |
| `modeling` | 2 | Visualizar/navegar (HU-6), editar arquitectura 3D (HU-7), import/export GLB/GLTF (HU-8) |
| `ai_design` | 2/3 | Diseñar plano con IA: texto/audio/asistente (HU-9) |
| `risk` | 2/3 | Detectar riesgos + sugerir mejoras (HU-10, Gemini) |
| `budget` | 3 | Materiales/calidad de bloques (HU-11), presupuesto (HU-12), revisión Ingeniero aprobar/observar/rechazar (HU-13) |
| `versioning` | 3 | Versionado tipo Git: commit, historial, restore, diff (HU-15) |
| `billing` | 3 | Suscripciones + pagos Stripe, webhook con verificación de firma (HU-17) |
| `sketch_2d` | 3 | Generar boceto 2D por prompt — app móvil (HU-18) |

> El proyecto se organiza en **3 sprints**. No existe Sprint 4: versionado, pagos y
> boceto 2D se entregan en el Sprint 3. En disco las apps de Sprint 3 viven en
> `apps/sprint_3/`.

## Stack

Python 3.11+, Django 5, DRF, **PostgreSQL** (sin sqlite), JWT (simplejwt, con refresh),
drf-spectacular (Swagger), django-cors-headers, Docker + docker-compose, pytest-django.

## Setup (local, con Postgres en Docker)

```bash
cd BACKEND
cp .env.example .env                 # ajusta credenciales si quieres

docker compose up -d db              # PostgreSQL (host port = DB_HOST_PORT, def. 5432)

python -m venv .venv
.venv\Scripts\activate               # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_users          # superadmin + 1 usuario por rol
python manage.py seed_projects       # proyectos demo
python manage.py seed_sample_plans   # plano + modelo 3D de ejemplo por proyecto
python manage.py seed_materials      # catálogo de materiales (calidad de bloques)
python manage.py seed_plans          # planes de suscripción (free/pro/enterprise)
python manage.py runserver           # http://127.0.0.1:8000
```

> Si ya tienes un Postgres local en 5432, pon `DB_HOST_PORT=55432` en `.env` y
> ajusta el puerto de `DATABASE_URL` a 55432 (evita un choque de puertos).

Usuarios sembrados (dev): `admin@arketo.dev / Admin12345` (superadmin),
`cliente@arketo.dev`, `arquitecto@arketo.dev`, `ingeniero@arketo.dev` (`Demo12345`).

## Setup (todo en Docker)

```bash
cp .env.example .env
docker compose up --build            # API en http://localhost:8000
```

## Documentación interactiva

- Swagger UI: **`/api/docs`**
- ReDoc: `/api/redoc`
- Esquema OpenAPI: `/api/schema`

## Endpoints (Sprint 1)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Registro (rol cliente) |
| POST | `/api/auth/login` | — | Login → `{access, refresh, user}` |
| POST | `/api/auth/refresh` | — | Renueva el access token (rota el refresh) |
| POST | `/api/auth/logout` | Bearer | Invalida el refresh token |
| GET/PATCH | `/api/auth/me` | Bearer | Ver / editar perfil |
| GET/POST/PUT/PATCH/DELETE | `/api/users/` | superadmin | CRUD de usuarios + roles |
| GET/POST/PUT/PATCH/DELETE | `/api/projects/` | Bearer | CRUD de proyectos (scoped al owner) |
| GET | `/api/projects/dashboard/` | Bearer | Resumen del dashboard (HU-16) |
| GET | `/api/projects/sync/` | Bearer | Sincronización incremental `?since=<ISO-8601>` (HU-16) |

## Endpoints (Sprint 2 — 2D→3D)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET/POST/DELETE | `/api/plans/` | Bearer | Subir/listar/borrar planos (`?project=<id>`) |
| POST | `/api/detection/run` | Bearer | Detección + generar 3D `{plan, detector?}` |
| GET | `/api/detection/jobs/` | Bearer | Historial de trabajos de detección |
| GET/DELETE | `/api/models3d/` | Bearer | Listar/ver/borrar modelos (`?project=<id>`) |
| PATCH | `/api/models3d/{id}/scene/` | Bearer | Editar arquitectura y regenerar el GLB |
| GET | `/api/models3d/{id}/export/` | Bearer | Exportar (URL del GLB) |
| POST | `/api/models3d/import/` | Bearer | Importar un GLB/GLTF externo |

> El detector por defecto es **`mock`** (funciona sin GPU/pesos). Para usar el
> modelo real: levanta `floorplan-api` y pon `DETECTION_DEFAULT_DETECTOR=maskrcnn`
> (o envía `"detector": "maskrcnn"` en `/api/detection/run`).

## Endpoints (Sprint 3 — IA y presupuesto)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/ai-design/text` | Bearer | Generar plano/3D desde texto |
| POST | `/api/ai-design/audio` | Bearer | Generar desde audio (se transcribe) |
| POST | `/api/ai-design/assistant` | Bearer | Asistente de diseño conversacional |
| GET | `/api/ai-design/requests/` | Bearer | Historial de generaciones |
| POST | `/api/risk/analyze` | Bearer | Analizar riesgos de un modelo 3D `{model3d}` |
| GET | `/api/risk/analyses/` | Bearer | Historial de análisis |
| GET/POST/… | `/api/material-categories/` · `/api/materials/` | lectura: auth · escritura: superadmin | Catálogo (calidad de bloques + precios) |
| GET/POST/DELETE | `/api/budgets/` | Bearer | Presupuestos (scoped) — calcula subtotales y total |
| POST | `/api/budgets/{id}/submit/` | Bearer | Enviar a revisión |
| POST | `/api/budgets/{id}/review/` | ingeniero | Revisión: aprobar/observar/rechazar |
| POST | `/api/sketch2d/generate` | Bearer | Generar boceto 2D por prompt (HU-18, móvil) |
| GET | `/api/sketch2d/` | Bearer | Bocetos del usuario |

> IA por defecto **`mock`** (sin claves). Para Gemini real: define `GEMINI_API_KEY`
> y pon `AI_DESIGN_PROVIDER=gemini` / `RISK_ANALYZER=gemini` / `SKETCH_PROVIDER=gemini`.

## Endpoints (Sprint 3 — colaboración, versionado y pagos)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET/POST | `/api/projects/{id}/members/` | Bearer (owner) | Listar/invitar colaboradores (editor/viewer) |
| DELETE | `/api/projects/{id}/members/{mid}/` | owner | Quitar colaborador |
| GET/POST/DELETE | `/api/comments/` | Bearer | Comentarios del proyecto (`?project=<id>`) |
| GET | `/api/versions/` | Bearer | Historial de versiones (`?project=<id>`) |
| POST | `/api/versions/commit/` | editor | Guardar versión (commit) `{project, message}` |
| POST | `/api/versions/{id}/restore/` | editor | Restaurar el proyecto a esa versión |
| GET | `/api/versions/diff/` | Bearer | Diff entre dos versiones `?from=<id>&to=<id>` (HU-15) |
| GET/POST | `/api/billing/plans/` | lectura: auth · escritura: superadmin | Planes de suscripción |
| GET | `/api/billing/subscription` | Bearer | Mi suscripción |
| POST | `/api/billing/subscribe` · `/api/billing/cancel` | Bearer | Suscribir/cambiar · cancelar |
| POST | `/api/billing/webhook` | — (firma Stripe) | Webhook Stripe: verifica firma HMAC y activa la suscripción |

> Colaboración: los **viewers** ven pero no editan (las escrituras exigen owner/editor).
> Pagos por defecto **mock** (`BILLING_GATEWAY=mock|stripe`); con Stripe real, el
> webhook (`STRIPE_WEBHOOK_SECRET`) activa la suscripción tras el pago.

## Tests

```bash
docker compose up -d db              # los tests usan Postgres
pytest
```

## Variables de entorno

Ver [`.env.example`](.env.example). Nada se hardcodea; PostgreSQL es obligatorio
(no hay fallback a sqlite).
