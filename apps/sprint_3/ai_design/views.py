"""AI design endpoints (CU9): generate from text/audio + conversational assistant."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsArquitecto

from . import services
from .models import AiConversation, DesignRequest
from .serializers import (
    AssistantSerializer,
    AudioDesignSerializer,
    ConversationSerializer,
    DesignRequestSerializer,
    TextDesignSerializer,
)


def _created(request_obj, http_request):
    return Response(
        DesignRequestSerializer(request_obj, context={"request": http_request}).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(tags=["ai-design"])
class GenerateFromTextView(APIView):
    permission_classes = [IsArquitecto]

    @extend_schema(request=TextDesignSerializer, responses={201: DesignRequestSerializer},
                   summary="Generar un plano/modelo 3D desde texto")
    def post(self, request):
        data = TextDesignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.generate_from_text(
            user=request.user,
            prompt=data.validated_data["prompt"],
            project_id=data.validated_data.get("project"),
            provider_name=data.validated_data.get("provider"),
        )
        return _created(result, request)


@extend_schema(tags=["ai-design"])
class GenerateFromAudioView(APIView):
    permission_classes = [IsArquitecto]

    @extend_schema(request=AudioDesignSerializer, responses={201: DesignRequestSerializer},
                   summary="Generar un plano desde audio (se transcribe y se reutiliza)")
    def post(self, request):
        data = AudioDesignSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.generate_from_audio(
            user=request.user,
            audio_file=data.validated_data["audio"],
            project_id=data.validated_data.get("project"),
            provider_name=data.validated_data.get("provider"),
        )
        return _created(result, request)


@extend_schema(tags=["ai-design"])
class AssistantView(APIView):
    permission_classes = [IsArquitecto]

    @extend_schema(request=AssistantSerializer, responses={201: DesignRequestSerializer},
                   summary="Asistente de diseño conversacional")
    def post(self, request):
        data = AssistantSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.assistant_reply(
            user=request.user,
            message=data.validated_data["message"],
            request_id=data.validated_data.get("request"),
            project_id=data.validated_data.get("project"),
            provider_name=data.validated_data.get("provider"),
        )
        return _created(result, request)


@extend_schema(tags=["ai-design"])
class ConversationView(APIView):
    """Historial del chat de Diseño con IA del usuario (persistido en la BD)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ConversationSerializer}, summary="Leer mi historial de chat IA")
    def get(self, request):
        conv = AiConversation.objects.filter(user=request.user).first()
        return Response({"turns": conv.turns if conv else []})

    @extend_schema(request=ConversationSerializer, responses={200: ConversationSerializer},
                   summary="Guardar mi historial de chat IA")
    def put(self, request):
        data = ConversationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        conv, _ = AiConversation.objects.update_or_create(
            user=request.user, defaults={"turns": data.validated_data["turns"]}
        )
        return Response({"turns": conv.turns})


@extend_schema(tags=["ai-design"])
class DesignRequestViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Read-only history of the caller's AI design requests."""

    serializer_class = DesignRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return DesignRequest.objects.none()
        return DesignRequest.objects.filter(user=user)
