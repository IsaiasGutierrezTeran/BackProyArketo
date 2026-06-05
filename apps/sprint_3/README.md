# Sprint 3 — Presupuesto, Colaboración, Pagos y Boceto 2D

| App | Casos de uso |
|-----|--------------|
| `ai_design` | HU-9 Diseñar plano con IA desde cero: por texto, por audio (speech-to-text), asistente |
| `risk` | HU-10 Detectar riesgos estructurales y sugerir mejoras (Gemini / Mock) |
| `budget` | HU-11 Materiales/calidad de bloques · HU-12 Presupuesto de obra · HU-13 Revisión del Ingeniero (aprobar/observar/rechazar) |
| `versioning` | HU-15 Versionado tipo Git: commit, historial, restaurar, diff (`ProjectVersion`) |
| `billing` | HU-17 Suscripciones + pagos Stripe (mejorar/degradar plan, webhook con verificación de firma) |
| `sketch_2d` | HU-18 Generar boceto 2D por prompt (app móvil): `Boceto2D`, `POST /api/sketch2d/generate` |
| `projects` *(extendida en Sprint 1)* | HU-14 Colaboración: `ProjectMembership` (roles owner/editor/viewer) + comentarios |

Proveedores de IA / pasarelas detrás de una interfaz, con **Mock por defecto** (sin
claves ni servicios externos):
`AI_DESIGN_PROVIDER`, `RISK_ANALYZER`, `SPEECH_TO_TEXT_PROVIDER`, `SKETCH_PROVIDER`
(`mock | gemini`) y `BILLING_GATEWAY` (`mock | stripe`).
Para Gemini real: define `GEMINI_API_KEY` y pon el proveedor en `gemini`.
Para Stripe real: define `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` y `BILLING_GATEWAY=stripe`.

`ai_design` y `risk` reutilizan `modeling` (crean/analizan `Model3D`). `budget` y
`versioning` son lógica de negocio pura. La colaboración (HU-14) vive en la app
`projects` (Sprint 1) porque todo cuelga del `Project`.

> El proyecto se organiza en **3 sprints**. No existe Sprint 4: versionado, pagos y
> boceto 2D se entregan dentro del Sprint 3.
