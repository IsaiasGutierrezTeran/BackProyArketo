# Sprint 1 — Base

Apps base de la plataforma. Cada una se importa por su nombre corto (`core`,
`accounts`, `projects`); ver `config/settings/base.py` (sys.path por sprint).

| App | Casos de uso |
|-----|--------------|
| `core` | Transversal: envelope `{success,data,meta}`, paginación, permisos, `BaseModel`, URLs absolutas, OpenAPI |
| `accounts` | Acceso (registro/login/logout/refresh), usuarios (CRUD superadmin), perfil, roles |
| `projects` | Project (entidad raíz) + dashboard (CU16); colaboración/comentarios se añaden en Sprint 4 |
