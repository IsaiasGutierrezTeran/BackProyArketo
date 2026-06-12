#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Borra lo que cuesta (EC2 + red/IAM/clave). Conserva S3 y ECR (datos) salvo
# que pases DELETE_DATA=1. La Elastic IP se libera (cobra si queda sin asociar).
#
# USO:         AWS_PROFILE=arketo bash deploy/aws/teardown.sh
# BORRAR TODO: AWS_PROFILE=arketo DELETE_DATA=1 bash deploy/aws/teardown.sh
# ──────────────────────────────────────────────────────────────────────────────
set -uo pipefail
export AWS_PROFILE="${AWS_PROFILE:-arketo}"
PROJECT="${PROJECT:-arketo}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SG_NAME="${PROJECT}-sg"
ROLE_NAME="${PROJECT}-ec2-role"
PROFILE_NAME="${PROJECT}-ec2-profile"
KEY_NAME="${PROJECT}-key"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf "\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()  { printf "\033[1;32m✔ %s\033[0m\n" "$*"; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || { echo "Credenciales AWS inválidas."; exit 1; }
echo "▶ Cuenta: $ACCOUNT_ID  ·  PROJECT=$PROJECT"
BUCKET="${PROJECT}-docs-${ACCOUNT_ID}-${AWS_REGION}"

# 1 · Instancias
IDS="$(aws ec2 describe-instances --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${PROJECT}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].InstanceId' --output text)"
if [[ -n "$IDS" ]]; then
  log "Terminando instancia(s): $IDS"
  aws ec2 terminate-instances --region "$AWS_REGION" --instance-ids $IDS >/dev/null
  aws ec2 wait instance-terminated --region "$AWS_REGION" --instance-ids $IDS
  ok "Instancia(s) terminada(s)."
else
  ok "No hay instancias vivas."
fi

# 2 · Elastic IP (libera para no cobrar)
EIP_ALLOC="$(aws ec2 describe-addresses --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${PROJECT}-eip" --query 'Addresses[0].AllocationId' --output text 2>/dev/null)"
if [[ -n "$EIP_ALLOC" && "$EIP_ALLOC" != "None" ]]; then
  aws ec2 release-address --region "$AWS_REGION" --allocation-id "$EIP_ALLOC" >/dev/null 2>&1 \
    && ok "Elastic IP liberada." || log "No pude liberar la EIP (¿asociada aún?)."
fi

# 3 · Security group
SG_ID="$(aws ec2 describe-security-groups --region "$AWS_REGION" \
  --filters "Name=group-name,Values=$SG_NAME" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)"
if [[ "$SG_ID" != "None" && -n "$SG_ID" ]]; then
  aws ec2 delete-security-group --region "$AWS_REGION" --group-id "$SG_ID" >/dev/null 2>&1 \
    && ok "Security group borrado." || log "SG aún en uso (reintenta en 1 min)."
fi

# 4 · IAM
aws iam remove-role-from-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME" >/dev/null 2>&1 || true
aws iam delete-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1 || true
aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-s3" >/dev/null 2>&1 || true
aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-ai" >/dev/null 2>&1 || true
aws iam detach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly >/dev/null 2>&1 || true
aws iam delete-role --role-name "$ROLE_NAME" >/dev/null 2>&1 && ok "Rol IAM borrado." || true

# 5 · Key pair
aws ec2 delete-key-pair --region "$AWS_REGION" --key-name "$KEY_NAME" >/dev/null 2>&1 || true
rm -f "$SCRIPT_DIR/${KEY_NAME}.pem" 2>/dev/null || true
ok "Key pair borrado."

# 6 · Datos (solo con DELETE_DATA=1)
if [[ "${DELETE_DATA:-0}" == "1" ]]; then
  log "Borrando datos (S3 + ECR)…"
  aws s3 rb "s3://${BUCKET}" --force >/dev/null 2>&1 && ok "Bucket S3 borrado." || true
  for repo in "${PROJECT}/backend" "${PROJECT}/floorapi" "${PROJECT}/maskrcnn"; do
    aws ecr delete-repository --region "$AWS_REGION" --repository-name "$repo" --force >/dev/null 2>&1 || true
  done
  ok "Repos ECR borrados."
else
  echo "ℹ  Bucket S3 ($BUCKET) y repos ECR conservados. Para borrarlos: DELETE_DATA=1 bash deploy/aws/teardown.sh"
fi
ok "Teardown completo. El gasto de cómputo se detuvo."
