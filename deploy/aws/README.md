# Despliegue de ARKETO en AWS (todo dentro de AWS)

Patrón: **ECR + S3 + rol IAM de instancia (sin claves) + EC2 con docker-compose + nginx + Caddy (HTTPS sslip.io)**.
Un solo comando idempotente crea todo en una cuenta AWS **nueva y aislada**.

## Qué levanta

Una EC2 (Amazon Linux 2023, `t3.large`) con docker-compose:

| Servicio   | Qué es                                   | Expuesto |
|------------|------------------------------------------|----------|
| `db`       | PostgreSQL 16 (volumen persistente)      | no (red interna) |
| `maskrcnn` | Flask + **Mask R-CNN real** (TF 1.15)    | no (interno; solo `floorapi`) |
| `floorapi` | FastAPI 2D→3D (`DETECTOR=maskrcnn`)      | no (interno; lo llama Django) |
| `backend`  | Django (migrate + gunicorn)              | vía nginx |
| `nginx`    | reverse proxy `:80` (`/api`, `/floor`)   | sí (80) |
| `caddy`    | TLS automático `:443` (dominio sslip.io) | sí (443) |

- **Almacenamiento:** Django guarda media en **S3 privado** (`django-storages` + `boto3`) con el **rol IAM de la EC2** (sin claves). URLs prefirmadas para que la app móvil/visor 3D carguen la media.
- **Detección:** Mask R-CNN **real** (los pesos `.h5` viven en S3; la EC2 los baja al arrancar y se montan en el contenedor — no van en la imagen).
- **IA del backend:** **AWS Bedrock** (Claude, `BEDROCK_MODEL_ID`) para diseño y riesgo, **AWS Transcribe** para voz→texto. Todo con el rol IAM (sin claves). Proveedor `aws` nuevo, conviviendo con `mock` (default en dev) y `gemini`.
- **HTTPS:** Caddy obtiene un certificado Let's Encrypt para `<ip-con-guiones>.sslip.io` (sin dominio propio), así el front HTTPS y Flutter consumen el backend sin *mixed-content/cleartext*.

## Aislamiento de cuenta (obligatorio)

- Todo recurso es **nuevo** y se prefija con `PROJECT=arketo` (no choca con otros proyectos).
- Corre **siempre** con el perfil dedicado: `AWS_PROFILE=arketo`.
- `deploy.sh` ejecuta `aws sts get-caller-identity`, **muestra el Account ID y EXIGE que lo reescribas** antes de crear nada. Si no coincide, aborta. (O pasa `CONFIRM_ACCOUNT_ID=<id>` para entornos no interactivos.)
- No hay claves AWS en ningún archivo: el backend usa el rol IAM de la instancia.

---

## ✅ Lo que TÚ pones (antes de correr el deploy)

1. **Credenciales del usuario IAM nuevo** en un perfil dedicado:
   ```bash
   aws configure --profile arketo      # Access Key / Secret de la cuenta NUEVA, región us-east-1
   aws sts get-caller-identity --profile arketo   # verifica que es la cuenta correcta
   ```
2. **Pesos del modelo** en `AIAPI/weights/maskrcnn_15_epochs.h5` (ya está en tu máquina).
   `deploy.sh` los sube a S3 y la EC2 los baja sola. (Override: `WEIGHTS_FILE=/ruta/al/.h5`.)
3. **Acceso a Bedrock** habilitado en `us-east-1` (consola AWS → Bedrock → *Model access* → habilita Claude, incl. el modelo de `BEDROCK_MODEL_ID`).
4. **Docker Desktop** corriendo y **AWS CLI** instalado.

---

## Cómo desplegar

```bash
# 1) Construye y prueba en local lo que quieras (opcional)
#    docker compose -f deploy/aws/docker-compose.prod.yml ... (necesita un .env)

# 2) Despliegue 1-comando (te pedirá confirmar el Account ID)
AWS_PROFILE=arketo bash deploy/aws/deploy.sh
#    Opcional: FRONT_ORIGIN=https://tu-front.vercel.app  (lo agrega a CORS)
```

Al terminar imprime la IP fija (Elastic IP) y las URLs:
- API: `https://<ip-guiones>.sslip.io/api/`
- Docs: `https://<ip-guiones>.sslip.io/api/docs`

Configura el **front Angular** y el **móvil Flutter** con `baseUrl = https://<ip-guiones>.sslip.io/api`.
(En Android emulador ya no uses `10.0.2.2`: apunta a la URL https pública.)

### Actualizar sin recrear la EC2
```bash
AWS_PROFILE=arketo bash deploy/aws/redeploy.sh   # rebuild+push+pull+up (conserva BD y .env)
```

### Apagar para no gastar
```bash
AWS_PROFILE=arketo bash deploy/aws/teardown.sh                 # borra EC2/EIP/SG/IAM/clave; conserva S3+ECR
AWS_PROFILE=arketo DELETE_DATA=1 bash deploy/aws/teardown.sh   # borra TAMBIÉN S3 + ECR
```

---

## Archivos

| Archivo | Para qué |
|---|---|
| `deploy.sh` | Crea TODO (ECR×3, S3, rol IAM, SG, key pair, Elastic IP, EC2 + user-data). Idempotente. |
| `redeploy.sh` | Rebuild+push de las 3 imágenes y pull+up en la EC2 existente. |
| `teardown.sh` | Borra el cómputo (y datos con `DELETE_DATA=1`). |
| `docker-compose.prod.yml` | El stack completo. |
| `nginx.conf` | `/api/`→django, `/floor/`→floorapi (strip), `/healthz`. maskrcnn no se expone. |
| `Caddyfile` | TLS sslip.io → nginx. **Lo genera `deploy.sh`** con la IP real (no se commitea). |
| `.env.example` | Referencia de lo que consume el stack (el `.env` real lo genera `deploy.sh` en la EC2). |

Imágenes / Dockerfiles:
- `backend` → `BackProyArketo/Dockerfile` (existe; Django env-driven).
- `floorapi` → `FloorApiArketo/Dockerfile` (existe).
- `maskrcnn` → `FastApiSw1Proyecto/Dockerfile` (**creado**: base `python:3.6.15`, TF1.15 desde `requirements.docker.txt`; pesos montados en runtime).

> Convención de rutas: este `deploy/aws/` vive en el repo del backend; `floorplan-api` y `AIAPI` se esperan como **carpetas hermanas**. Si tus clones tienen otros nombres/rutas, pásalos por env: `FLOORAPI_DIR=...`, `MASKRCNN_DIR=...`.

## Notas

- **Primera detección lenta:** el modelo TF1.15 carga en la 1ª petición (~30-60s). `FALLBACK_TO_OPENCV=true` evita que un fallo del modelo tumbe el flujo.
- **Compatibilidad dev:** nada cambia para correr local con `mock` (S3 off, IA mock). Los proveedores `aws` solo se activan por env (`AI_DESIGN_PROVIDER=aws`, etc.).
- **Sembrar demo (opcional):** `ssh` a la EC2 y `cd /opt/arketo && sudo docker compose exec backend python manage.py seed_demo`.
- **Seguridad:** `*.pem`, `Caddyfile` y `.env` están en `.gitignore` de esta carpeta. Las claves IAM nunca se escriben en disco del repo.
