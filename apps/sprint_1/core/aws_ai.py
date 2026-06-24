"""AWS managed-AI clients used by the "aws" providers (opt-in).

- Bedrock (Claude, Anthropic Messages API) for text/design/risk generation.
- Transcribe for speech-to-text.

Credentials are NOT read from settings: boto3 resolves them from the default
chain, which on the EC2 instance is the attached IAM role (no keys). Region and
the Bedrock model id come from settings. Kept lazy so importing this module never
forces boto3 at startup and dev (mock provider) stays offline.
"""

from __future__ import annotations

import json
import time
import uuid

from django.conf import settings

from .exceptions import ApiException


def _region() -> str:
    return getattr(settings, "AWS_REGION", None) or getattr(
        settings, "AWS_S3_REGION_NAME", "us-east-1"
    )


def _client(service: str):
    import boto3  # lazy: only when the aws provider is actually used

    return boto3.client(service, region_name=_region())


def bedrock_generate_text(
    prompt: str,
    *,
    system: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.2,
) -> str:
    """Invoke a Claude model on Bedrock and return the concatenated text.

    Uses the Anthropic Messages API shape required by Bedrock InvokeModel
    (``anthropic_version: "bedrock-2023-05-31"``). Model id from
    ``settings.BEDROCK_MODEL_ID`` (e.g. a Claude Haiku 4.5 inference profile).
    """
    model_id = getattr(
        settings,
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    body: dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    try:
        import boto3
        from botocore.config import Config

        # Pocos reintentos: si la cuota está en 0 (cuenta nueva) el throttle es
        # definitivo, así el fallback del proveedor responde casi al instante;
        # read_timeout amplio porque una generación real de Claude puede tardar.
        client = boto3.client(
            "bedrock-runtime",
            region_name=_region(),
            config=Config(
                retries={"max_attempts": 2, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            ),
        )
        resp = client.invoke_model(modelId=model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
    except Exception as exc:  # boto3 ClientError, JSON, etc.
        raise ApiException(
            "No se pudo contactar el servicio de IA (AWS Bedrock).",
            code="inference_error",
            status_code=502,
        ) from exc
    blocks = payload.get("content", []) or []
    text = "".join(
        b.get("text", "") for b in blocks if b.get("type") == "text"
    )
    if not text.strip():
        raise ApiException(
            "Respuesta vacía del servicio de IA (AWS Bedrock).",
            code="inference_error",
            status_code=502,
        )
    return text


def transcribe_audio(
    audio_bytes: bytes, *, filename: str = "audio", timeout: float = 120.0
) -> str:
    """Transcribe audio with AWS Transcribe (async job + poll) and return text.

    Uploads the clip to the project S3 bucket, starts a transcription job that
    writes its result back to the bucket, polls until it finishes, then reads
    the transcript. Uses the instance role for S3 + Transcribe (no keys).
    """
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    if not bucket:
        raise ApiException(
            "AWS_STORAGE_BUCKET_NAME es requerido para AWS Transcribe.",
            code="bad_request",
            status_code=400,
        )
    language = getattr(settings, "TRANSCRIBE_LANGUAGE", "es-US")
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "mp3").lower()
    media_format = {
        "m4a": "mp4",
        "mp4": "mp4",
        "mp3": "mp3",
        "wav": "wav",
        "ogg": "ogg",
        "oga": "ogg",
        "webm": "webm",
        "flac": "flac",
        "amr": "amr",
    }.get(ext, "mp3")

    job = f"arketo-stt-{uuid.uuid4().hex}"
    in_key = f"transcribe-input/{job}.{ext}"
    out_key = f"transcribe-output/{job}.json"

    s3 = _client("s3")
    tr = _client("transcribe")
    try:
        s3.put_object(Bucket=bucket, Key=in_key, Body=audio_bytes)
        tr.start_transcription_job(
            TranscriptionJobName=job,
            LanguageCode=language,
            MediaFormat=media_format,
            Media={"MediaFileUri": f"s3://{bucket}/{in_key}"},
            OutputBucketName=bucket,
            OutputKey=out_key,
        )
        deadline = time.monotonic() + timeout
        status = "IN_PROGRESS"
        while time.monotonic() < deadline:
            info = tr.get_transcription_job(TranscriptionJobName=job)
            status = info["TranscriptionJob"]["TranscriptionJobStatus"]
            if status in ("COMPLETED", "FAILED"):
                break
            time.sleep(3)
        if status != "COMPLETED":
            raise ApiException(
                "La transcripción (AWS Transcribe) no completó a tiempo.",
                code="inference_error",
                status_code=504,
            )
        result = json.loads(
            s3.get_object(Bucket=bucket, Key=out_key)["Body"].read()
        )
        return result["results"]["transcripts"][0]["transcript"]
    except ApiException:
        raise
    except Exception as exc:
        raise ApiException(
            "Fallo en la transcripción (AWS Transcribe).",
            code="inference_error",
            status_code=502,
        ) from exc
    finally:
        # Best-effort cleanup (no claves, no rastro).
        try:
            tr.delete_transcription_job(TranscriptionJobName=job)
        except Exception:
            pass
        try:
            s3.delete_object(Bucket=bucket, Key=in_key)
        except Exception:
            pass
