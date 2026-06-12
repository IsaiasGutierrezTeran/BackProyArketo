#!/usr/bin/env bash
# Redeploy a la EC2 EXISTENTE (sin recrearla): rebuild + push de las 3 imágenes a
# ECR y pull + up -d en la instancia. NO regenera el .env (conserva DB y secretos).
#
# USO: AWS_PROFILE=arketo bash deploy/aws/redeploy.sh
set -euo pipefail
export AWS_PROFILE="${AWS_PROFILE:-arketo}"
PROJECT="${PROJECT:-arketo}"
AWS_REGION="${AWS_REGION:-us-east-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${BACKEND_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
WORKSPACE_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
FLOORAPI_DIR="${FLOORAPI_DIR:-$WORKSPACE_DIR/floorplan-api}"
MASKRCNN_DIR="${MASKRCNN_DIR:-$WORKSPACE_DIR/AIAPI}"
KEY="$SCRIPT_DIR/${PROJECT}-key.pem"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "▶ Cuenta: $ACCOUNT_ID  ·  perfil: $AWS_PROFILE  ·  PROJECT=$PROJECT"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_BACKEND="${REGISTRY}/${PROJECT}/backend:latest"
ECR_FLOORAPI="${REGISTRY}/${PROJECT}/floorapi:latest"
ECR_MASKRCNN="${REGISTRY}/${PROJECT}/maskrcnn:latest"

IP="$(aws ec2 describe-instances --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${PROJECT}" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
[[ -n "$IP" && "$IP" != "None" ]] || { echo "No hay instancia '${PROJECT}' encendida."; exit 1; }
echo "▶ Instancia: $IP"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
echo "▶ ECR login OK"

export DOCKER_DEFAULT_PLATFORM=linux/amd64
echo "▶ Build + push (3 imágenes)…"
docker build --platform linux/amd64 -t "$ECR_BACKEND"  -f "$BACKEND_DIR/Dockerfile"  "$BACKEND_DIR"
docker build --platform linux/amd64 -t "$ECR_FLOORAPI" -f "$FLOORAPI_DIR/Dockerfile" "$FLOORAPI_DIR"
docker build --platform linux/amd64 -t "$ECR_MASKRCNN" -f "$MASKRCNN_DIR/Dockerfile" "$MASKRCNN_DIR"
docker push "$ECR_BACKEND"
docker push "$ECR_FLOORAPI"
docker push "$ECR_MASKRCNN"

# Copia compose + nginx + Caddyfile actualizados (no toca .env), re-login y pull+up.
scp $SSHOPTS -i "$KEY" "$SCRIPT_DIR/nginx.conf"             ec2-user@"$IP":/tmp/nginx.conf >/dev/null
scp $SSHOPTS -i "$KEY" "$SCRIPT_DIR/docker-compose.prod.yml" ec2-user@"$IP":/tmp/dc.yml    >/dev/null
[[ -f "$SCRIPT_DIR/Caddyfile" ]] && scp $SSHOPTS -i "$KEY" "$SCRIPT_DIR/Caddyfile" ec2-user@"$IP":/tmp/Caddyfile >/dev/null
ssh $SSHOPTS -i "$KEY" ec2-user@"$IP" "
  sudo cp /tmp/nginx.conf /opt/${PROJECT}/nginx.conf
  sudo cp /tmp/dc.yml     /opt/${PROJECT}/docker-compose.yml
  [ -f /tmp/Caddyfile ] && sudo cp /tmp/Caddyfile /opt/${PROJECT}/Caddyfile || true
  aws ecr get-login-password --region $AWS_REGION | sudo docker login --username AWS --password-stdin $REGISTRY >/dev/null
  cd /opt/${PROJECT}
  sudo docker compose pull 2>&1 | tail -4
  sudo docker compose up -d 2>&1 | tail -8
" 2>&1 | grep -viE "Warning: Permanently|Permanently added"
echo "✔ Redeploy completo: https://$(echo "$IP" | tr '.' '-').sslip.io/api/"
