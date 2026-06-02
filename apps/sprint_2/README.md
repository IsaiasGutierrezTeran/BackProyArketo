# Sprint 2 — Digitalización 2D → 3D

Pipeline: subir plano → detección IA → generación del modelo 3D (.glb) →
visualizar / editar.

| App | Casos de uso |
|-----|--------------|
| `plans` | CU4 Subir y validar plano (PDF/JPG/PNG/CSV) |
| `detection` | CU5 Generar 3D: detector (Mask R-CNN vía `floorplan-api`, o Mock) + GLB con trimesh |
| `modeling` | CU6 Visualizar/navegar · CU7 Editar arquitectura 3D · CU8 Import/Export GLB/GLTF |

Pipeline (3 capas): `detection` → `floorplan-api` (HTTP, normaliza) → `AIAPI`
(Mask R-CNN). Por defecto el detector es **mock**, así el pipeline funciona sin
GPU/pesos/servicio legacy. Cambia con `DETECTION_DEFAULT_DETECTOR=maskrcnn`.
