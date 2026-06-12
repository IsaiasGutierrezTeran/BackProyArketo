#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Despliegue 1-comando del stack ARKETO en AWS (todo dentro de AWS):
#   ECR (3 imágenes) · S3 (media + pesos del modelo) · IAM (rol de instancia,
#   sin claves) · EC2 con docker-compose: postgres + django + floorapi +
#   maskrcnn(interno) + nginx + caddy(HTTPS sslip.io).
#
# AISLAMIENTO DE CUENTA (importante):
#   - Corre SIEMPRE con un perfil dedicado:  AWS_PROFILE=arketo
#   - Antes de crear nada, muestra el Account ID y EXIGE confirmación.
#   - PROJECT=arketo prefija TODOS los recursos (no choca con otros proyectos).
#
# REQUISITOS (los pones tú UNA vez):
#   1. `aws configure --profile arketo` con las credenciales de la cuenta NUEVA.
#   2. Docker Desktop corriendo (para construir las imágenes).
#   3. El archivo de pesos del modelo en  AIAPI/weights/maskrcnn_15_epochs.h5
#   4. Acceso a los modelos de Bedrock habilitado en us-east-1 (consola AWS).
#
# USO:    AWS_PROFILE=arketo bash deploy/aws/deploy.sh
# LIMPIA: AWS_PROFILE=arketo bash deploy/aws/teardown.sh
#
# Variables opcionales (export antes de correr):
#   AWS_REGION (us-east-1) · INSTANCE_TYPE (t3.large) · PROJECT (arketo)
#   FRONT_ORIGIN (URL del front Angular para CORS, ej. https://arketo.vercel.app)
#   CONFIRM_ACCOUNT_ID (si lo pones y coincide, salta la pregunta interactiva)
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
export AWS_PROFILE="${AWS_PROFILE:-arketo}"
PROJECT="${PROJECT:-arketo}"
AWS_REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"   # 8 GB RAM + swap: holgura para TF1.15 + Postgres + Django.
COMPOSE_VERSION="v2.29.7"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
FRONT_ORIGIN="${FRONT_ORIGIN:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# El repo del backend (BackProyArketo) contiene este deploy/aws/.
BACKEND_DIR="${BACKEND_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
WORKSPACE_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
# Los otros dos repos viven como hermanos del backend (configurable por env).
FLOORAPI_DIR="${FLOORAPI_DIR:-$WORKSPACE_DIR/floorplan-api}"
MASKRCNN_DIR="${MASKRCNN_DIR:-$WORKSPACE_DIR/AIAPI}"
WEIGHTS_FILE="${WEIGHTS_FILE:-$MASKRCNN_DIR/weights/maskrcnn_15_epochs.h5}"

SG_NAME="${PROJECT}-sg"
ROLE_NAME="${PROJECT}-ec2-role"
PROFILE_NAME="${PROJECT}-ec2-profile"
KEY_NAME="${PROJECT}-key"
KEY_FILE="$SCRIPT_DIR/${KEY_NAME}.pem"

log()  { printf "\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✔ %s\033[0m\n" "$*"; }
die()  { printf "\033[1;31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

# ── 0 · Preflight ─────────────────────────────────────────────────────────────
command -v aws    >/dev/null || die "AWS CLI no instalado."
command -v docker >/dev/null || die "Docker no instalado."
docker info >/dev/null 2>&1   || die "Docker no está corriendo (arráncalo)."
[[ -d "$BACKEND_DIR"  ]] || die "No encuentro el repo backend en $BACKEND_DIR"
[[ -d "$FLOORAPI_DIR" ]] || die "No encuentro floorplan-api en $FLOORAPI_DIR (export FLOORAPI_DIR=...)."
[[ -d "$MASKRCNN_DIR" ]] || die "No encuentro AIAPI (maskrcnn) en $MASKRCNN_DIR (export MASKRCNN_DIR=...)."
[[ -f "$WEIGHTS_FILE" ]] || die "Falta el archivo de pesos: $WEIGHTS_FILE
   Déjalo ahí (o export WEIGHTS_FILE=/ruta/al/maskrcnn_15_epochs.h5) y reintenta."

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "Credenciales AWS inválidas. Corre 'aws configure --profile $AWS_PROFILE'."
CALLER_ARN="$(aws sts get-caller-identity --query Arn --output text)"

# ── 0a · GATE de aislamiento de cuenta ────────────────────────────────────────
printf "\n\033[1;33m──────────── CONFIRMA LA CUENTA ANTES DE CREAR NADA ────────────\033[0m\n"
printf "  Perfil AWS   : %s\n" "$AWS_PROFILE"
printf "  Account ID   : \033[1m%s\033[0m\n" "$ACCOUNT_ID"
printf "  Usuario (ARN): %s\n" "$CALLER_ARN"
printf "  Región       : %s   ·   PROJECT=%s\n" "$AWS_REGION" "$PROJECT"
printf "\033[1;33m────────────────────────────────────────────────────────────────\033[0m\n"
if [[ -n "${CONFIRM_ACCOUNT_ID:-}" ]]; then
  [[ "$CONFIRM_ACCOUNT_ID" == "$ACCOUNT_ID" ]] \
    || die "CONFIRM_ACCOUNT_ID ($CONFIRM_ACCOUNT_ID) != cuenta actual ($ACCOUNT_ID). Abortado."
  ok "Cuenta confirmada por CONFIRM_ACCOUNT_ID."
else
  read -r -p "¿Es esta la cuenta NUEVA de Arketo? Reescribe el Account ID para continuar: " TYPED
  [[ "$TYPED" == "$ACCOUNT_ID" ]] || die "No coincide. Abortado para no tocar otra cuenta."
fi

REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_BACKEND="${REGISTRY}/${PROJECT}/backend:latest"
ECR_FLOORAPI="${REGISTRY}/${PROJECT}/floorapi:latest"
ECR_MASKRCNN="${REGISTRY}/${PROJECT}/maskrcnn:latest"
BUCKET="${PROJECT}-docs-${ACCOUNT_ID}-${AWS_REGION}"
WEIGHTS_KEY="model-weights/maskrcnn_15_epochs.h5"

# Evita lanzar una segunda instancia si ya hay una viva.
EXISTING="$(aws ec2 describe-instances --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${PROJECT}" "Name=instance-state-name,Values=pending,running" \
  --query 'Reservations[].Instances[].InstanceId' --output text)"
if [[ -n "$EXISTING" ]]; then
  die "Ya hay una instancia '${PROJECT}' viva ($EXISTING). Usa redeploy.sh o teardown.sh primero."
fi

# ── 0b · Elastic IP estática (idempotente) ────────────────────────────────────
EIP_ALLOC="$(aws ec2 describe-addresses --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${PROJECT}-eip" --query 'Addresses[0].AllocationId' --output text 2>/dev/null)"
if [[ "$EIP_ALLOC" == "None" || -z "$EIP_ALLOC" ]]; then
  read -r EIP_ALLOC STATIC_IP < <(aws ec2 allocate-address --region "$AWS_REGION" --domain vpc \
    --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=${PROJECT}-eip}]" \
    --query '[AllocationId,PublicIp]' --output text)
else
  STATIC_IP="$(aws ec2 describe-addresses --region "$AWS_REGION" --allocation-ids "$EIP_ALLOC" \
    --query 'Addresses[0].PublicIp' --output text)"
fi
ok "Elastic IP estática: $STATIC_IP ($EIP_ALLOC)"
SSLIP_DOMAIN="$(echo "$STATIC_IP" | tr '.' '-').sslip.io"
PUBLIC_BASE_URL="https://${SSLIP_DOMAIN}"

# ── 1 · ECR: repos + build + push (3 imágenes) ────────────────────────────────
log "ECR: asegurando repositorios e iniciando sesión…"
for repo in "${PROJECT}/backend" "${PROJECT}/floorapi" "${PROJECT}/maskrcnn"; do
  aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$repo" >/dev/null 2>&1 \
    || aws ecr create-repository --region "$AWS_REGION" --repository-name "$repo" \
         --image-scanning-configuration scanOnPush=true >/dev/null
done
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
ok "ECR listo."

export DOCKER_DEFAULT_PLATFORM=linux/amd64
log "Construyendo backend Django (env-driven, no se hornea config)…"
docker build --platform linux/amd64 -t "$ECR_BACKEND" -f "$BACKEND_DIR/Dockerfile" "$BACKEND_DIR"
log "Construyendo floorapi (FastAPI)…"
docker build --platform linux/amd64 -t "$ECR_FLOORAPI" -f "$FLOORAPI_DIR/Dockerfile" "$FLOORAPI_DIR"
log "Construyendo maskrcnn (Flask + TF1.15, ~varios min la 1a vez)…"
docker build --platform linux/amd64 -t "$ECR_MASKRCNN" -f "$MASKRCNN_DIR/Dockerfile" "$MASKRCNN_DIR"
log "Subiendo imágenes a ECR…"
docker push "$ECR_BACKEND"
docker push "$ECR_FLOORAPI"
docker push "$ECR_MASKRCNN"
ok "Imágenes en ECR."

# ── 2 · S3: bucket privado (media + pesos del modelo) ─────────────────────────
log "S3: asegurando bucket $BUCKET…"
if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  fi
fi
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true >/dev/null
ok "Bucket S3 privado listo."

log "Subiendo pesos del modelo a s3://$BUCKET/$WEIGHTS_KEY (244 MB, una vez)…"
aws s3 cp "$WEIGHTS_FILE" "s3://${BUCKET}/${WEIGHTS_KEY}" --only-show-errors
ok "Pesos en S3 (la EC2 los baja al arrancar; no van en la imagen)."

# ── 3 · IAM: rol de instancia (S3 + Bedrock + Transcribe + ECR readonly) ──────
log "IAM: asegurando rol de instancia…"
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }' >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-s3" --policy-document "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{
    \"Effect\":\"Allow\",
    \"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\",\"s3:ListBucket\"],
    \"Resource\":[\"arn:aws:s3:::${BUCKET}\",\"arn:aws:s3:::${BUCKET}/*\"]
  }]
}" >/dev/null
# IA gestionada: Bedrock (Claude) para diseño/riesgo + Transcribe para STT.
# Resource:* en bedrock evita adivinar el ARN del perfil de inferencia.
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-ai" --policy-document '{
  "Version":"2012-10-17",
  "Statement":[
    {"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":"*"},
    {"Effect":"Allow","Action":["transcribe:StartTranscriptionJob","transcribe:GetTranscriptionJob","transcribe:DeleteTranscriptionJob","transcribe:ListTranscriptionJobs"],"Resource":"*"}
  ]
}' >/dev/null
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly >/dev/null 2>&1 || true
if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME" >/dev/null
  log "Esperando propagación del instance profile (10s)…"; sleep 10
fi
ok "Rol IAM listo (el backend usará S3/Bedrock/Transcribe sin claves)."

# ── 4 · Red: security group en la VPC por defecto ─────────────────────────────
log "EC2: asegurando security group…"
VPC_ID="$(aws ec2 describe-vpcs --region "$AWS_REGION" \
  --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[[ "$VPC_ID" != "None" && -n "$VPC_ID" ]] || die "No hay VPC por defecto en $AWS_REGION."
SG_ID="$(aws ec2 describe-security-groups --region "$AWS_REGION" \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)"
if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
  SG_ID="$(aws ec2 create-security-group --region "$AWS_REGION" --group-name "$SG_NAME" \
    --description "Arketo stack" --vpc-id "$VPC_ID" --query GroupId --output text)"
  for port in 22 80 443; do
    aws ec2 authorize-security-group-ingress --region "$AWS_REGION" --group-id "$SG_ID" \
      --protocol tcp --port "$port" --cidr 0.0.0.0/0 >/dev/null
  done
fi
ok "Security group: $SG_ID (22/80/443 abiertos)."

# ── 5 · Key pair (SSH de diagnóstico) ─────────────────────────────────────────
if ! aws ec2 describe-key-pairs --region "$AWS_REGION" --key-names "$KEY_NAME" >/dev/null 2>&1; then
  log "Creando key pair $KEY_NAME…"
  aws ec2 create-key-pair --region "$AWS_REGION" --key-name "$KEY_NAME" \
    --query KeyMaterial --output text > "$KEY_FILE"
  chmod 400 "$KEY_FILE" 2>/dev/null || true
  ok "Clave SSH guardada en $KEY_FILE"
else
  ok "Key pair $KEY_NAME ya existe."
fi

# ── 6 · .env + Caddyfile + user-data ──────────────────────────────────────────
# Secretos de demo (NO van al repo; viven solo en la instancia).
DJANGO_SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n=+/' )$(openssl rand -hex 8)"
POSTGRES_DB="arketo"
POSTGRES_USER="arketo"
POSTGRES_PASSWORD="$(openssl rand -hex 16)"
CORS_ORIGINS="http://localhost:4200,http://127.0.0.1:4200"
[[ -n "$FRONT_ORIGIN" ]] && CORS_ORIGINS="${FRONT_ORIGIN},${CORS_ORIGINS}"

ENV_CONTENT="# Generado por deploy.sh — NO commitear. Solo vive en la EC2.
ECR_BACKEND=${ECR_BACKEND}
ECR_FLOORAPI=${ECR_FLOORAPI}
ECR_MASKRCNN=${ECR_MASKRCNN}

# Django
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${SSLIP_DOMAIN},${STATIC_IP},localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://${SSLIP_DOMAIN},http://${STATIC_IP}
CORS_ALLOWED_ORIGINS=${CORS_ORIGINS}
PUBLIC_BASE_URL=${PUBLIC_BASE_URL}

# Postgres (interno; sin puerto expuesto)
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
DATABASE_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

# Almacenamiento S3 (bucket privado, rol IAM, sin claves)
USE_S3=true
AWS_STORAGE_BUCKET_NAME=${BUCKET}
AWS_S3_REGION_NAME=${AWS_REGION}
AWS_REGION=${AWS_REGION}
AWS_QUERYSTRING_AUTH=true

# Detección 2D->3D: Mask R-CNN real
DETECTION_DEFAULT_DETECTOR=maskrcnn
FLOORPLAN_API_URL=http://floorapi:8000
FLOORPLAN_API_TIMEOUT=180
FLOOR_DETECTOR=maskrcnn
MASKRCNN_LEGACY_URL=http://maskrcnn:5000/

# IA del backend con AWS Bedrock + Transcribe
AI_DESIGN_PROVIDER=aws
RISK_ANALYZER=aws
SPEECH_TO_TEXT_PROVIDER=aws
SKETCH_PROVIDER=mock
BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID}
TRANSCRIBE_LANGUAGE=es-US

# Caddy (HTTPS sslip.io)
SSLIP_DOMAIN=${SSLIP_DOMAIN}"

# Caddyfile con el dominio sslip.io horneado (para redeploy.sh lo deja en disco).
CADDY_CONTENT="${SSLIP_DOMAIN} {
	reverse_proxy nginx:80
}"
printf '%s\n' "$CADDY_CONTENT" > "$SCRIPT_DIR/Caddyfile"

COMPOSE_FILE="$SCRIPT_DIR/docker-compose.prod.yml"
NGINX_FILE="$SCRIPT_DIR/nginx.conf"
b64() { base64 -w0 "$1" 2>/dev/null || base64 "$1" | tr -d '\n'; }
b64s() { printf '%s' "$1" | { base64 -w0 2>/dev/null || base64 | tr -d '\n'; }; }
B64_COMPOSE="$(b64 "$COMPOSE_FILE")"
B64_NGINX="$(b64 "$NGINX_FILE")"
B64_CADDY="$(b64s "$CADDY_CONTENT")"
B64_ENV="$(b64s "$ENV_CONTENT")"

USER_DATA="$(cat <<USERDATA
#!/bin/bash
set -xe
exec > /var/log/${PROJECT}-init.log 2>&1

# Swap de 4 GB (TF1.15 carga ~2-3 GB al inferir).
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

dnf install -y docker
systemctl enable --now docker
mkdir -p /usr/libexec/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64 \
  -o /usr/libexec/docker/cli-plugins/docker-compose
chmod +x /usr/libexec/docker/cli-plugins/docker-compose

mkdir -p /opt/${PROJECT}/weights && cd /opt/${PROJECT}
echo ${B64_COMPOSE} | base64 -d > docker-compose.yml
echo ${B64_NGINX}   | base64 -d > nginx.conf
echo ${B64_CADDY}   | base64 -d > Caddyfile
echo ${B64_ENV}     | base64 -d > .env

# Pesos del modelo desde S3 (usa el rol de la instancia).
aws s3 cp s3://${BUCKET}/${WEIGHTS_KEY} /opt/${PROJECT}/weights/maskrcnn_15_epochs.h5 --region ${AWS_REGION}

aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${REGISTRY}
docker compose --env-file .env -f docker-compose.yml pull
docker compose --env-file .env -f docker-compose.yml up -d
echo "ARKETO_INIT_DONE"
USERDATA
)"

# ── 7 · Lanzar EC2 ────────────────────────────────────────────────────────────
log "Resolviendo AMI Amazon Linux 2023…"
AMI_ID="$(aws ssm get-parameters --region "$AWS_REGION" \
  --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameters[0].Value' --output text 2>/dev/null || true)"
if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
  AMI_ID="$(aws ec2 describe-images --region "$AWS_REGION" --owners amazon \
    --filters "Name=name,Values=al2023-ami-2023.*-kernel-*-x86_64" \
              "Name=state,Values=available" "Name=architecture,Values=x86_64" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text 2>/dev/null || true)"
fi
[[ -n "$AMI_ID" && "$AMI_ID" != "None" ]] || die "No pude resolver la AMI de Amazon Linux 2023."
ok "AMI: $AMI_ID"

log "Lanzando instancia $INSTANCE_TYPE…"
INSTANCE_ID="$(aws ec2 run-instances --region "$AWS_REGION" \
  --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" --security-group-ids "$SG_ID" \
  --iam-instance-profile Name="$PROFILE_NAME" \
  --metadata-options 'HttpTokens=optional,HttpPutResponseHopLimit=2,HttpEndpoint=enabled' \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --user-data "$USER_DATA" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${PROJECT}}]" \
  --query 'Instances[0].InstanceId' --output text)"
ok "Instancia: $INSTANCE_ID"

log "Esperando a que arranque…"
aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"
log "Asociando Elastic IP estática $STATIC_IP…"
aws ec2 associate-address --region "$AWS_REGION" \
  --instance-id "$INSTANCE_ID" --allocation-id "$EIP_ALLOC" >/dev/null

cat <<RESUMEN

────────────────────────────────────────────────────────────────────────────
✔ DESPLIEGUE LANZADO  (cuenta $ACCOUNT_ID)
  Instancia : $INSTANCE_ID   ·   IP fija: $STATIC_IP
  Bucket S3 : $BUCKET
  Imágenes  : $ECR_BACKEND
              $ECR_FLOORAPI
              $ECR_MASKRCNN

  Tarda ~5-8 min (instala Docker, baja imágenes/pesos y arranca; el modelo
  TF1.15 carga en la 1a petición de detección, ~30-60s).
  Cuando termine:
    • API        →  ${PUBLIC_BASE_URL}/api/
    • Swagger    →  ${PUBLIC_BASE_URL}/api/docs
    • Health     →  ${PUBLIC_BASE_URL}/healthz
    • floorapi   →  ${PUBLIC_BASE_URL}/floor/health   (interno; útil para test)

  Configura el front Angular y el móvil Flutter con baseUrl:
    ${PUBLIC_BASE_URL}/api

  Ver progreso del arranque (SSH):
    ssh -i "$KEY_FILE" ec2-user@$STATIC_IP "tail -f /var/log/${PROJECT}-init.log"

  Para APAGAR y dejar de gastar:  AWS_PROFILE=$AWS_PROFILE bash deploy/aws/teardown.sh
────────────────────────────────────────────────────────────────────────────
RESUMEN
