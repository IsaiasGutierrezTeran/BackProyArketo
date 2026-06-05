"""Speech-to-text behind an interface (mock by default)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from django.conf import settings

from core.exceptions import ApiException


class TranscriberBase(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, *, filename: str = "audio") -> str:
        raise NotImplementedError


class MockTranscriber(TranscriberBase):
    name = "mock"

    def transcribe(self, audio_bytes: bytes, *, filename: str = "audio") -> str:
        # Deterministic transcript so the audio->design path works offline.
        return "Una casa de 6 por 4 metros con una puerta al frente."


class GeminiTranscriber(TranscriberBase):
    name = "gemini"

    def transcribe(self, audio_bytes: bytes, *, filename: str = "audio") -> str:
        # Real audio transcription needs the Gemini Files API / multimodal upload;
        # left as a clear, explicit gap rather than fabricating a transcript.
        raise ApiException(
            "Transcripción Gemini aún no implementada; usa SPEECH_TO_TEXT_PROVIDER=mock.",
            code="not_implemented", status_code=501,
        )


class AwsTranscriber(TranscriberBase):
    name = "aws"

    def transcribe(self, audio_bytes: bytes, *, filename: str = "audio") -> str:
        # Real STT via AWS Transcribe (uses the EC2 instance role, no keys).
        from core.aws_ai import transcribe_audio

        return transcribe_audio(audio_bytes, filename=filename)


_TRANSCRIBERS: dict[str, type[TranscriberBase]] = {
    "mock": MockTranscriber,
    "gemini": GeminiTranscriber,
    "aws": AwsTranscriber,
}


def get_transcriber(name: str | None = None) -> TranscriberBase:
    name = name or settings.SPEECH_TO_TEXT_PROVIDER
    cls = _TRANSCRIBERS.get(name, MockTranscriber)
    return cls()
