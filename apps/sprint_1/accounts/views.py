"""Auth + user-management endpoints. Views orchestrate; logic is in services.

Auth flow (identical for Angular and Flutter — Bearer access token):

    POST /api/auth/register   -> create account (role=cliente)
    POST /api/auth/login       -> {access, refresh, user}
    POST /api/auth/refresh     -> {access}        (rotates + blacklists old refresh)
    POST /api/auth/logout      -> blacklist a refresh token
    GET/PATCH /api/auth/me     -> read / edit own profile
    /api/users/ (superadmin)   -> full user CRUD + role management
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from core.permissions import IsSuperAdmin

from . import services
from .serializers import (
    AdminUserSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


@extend_schema(tags=["auth"])
class RegisterView(APIView):
    """Public self-registration."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserSerializer},
        summary="Registrar un nuevo usuario (rol cliente)",
    )
    def post(self, request):
        serializer = RegisterSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = services.register_user(**serializer.validated_data)
        return Response(
            UserSerializer(user, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["auth"], summary="Iniciar sesión (devuelve access, refresh y user)"
)
class LoginView(TokenObtainPairView):
    """Email + password -> {access, refresh, user}. Rate-limited (HU-2)."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"


@extend_schema(tags=["auth"])
class LogoutView(APIView):
    """Blacklist the supplied refresh token."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
            }
        },
        responses={200: OpenApiResponse(description="Sesión cerrada.")},
        summary="Cerrar sesión (invalida el refresh token)",
    )
    def post(self, request):
        services.logout(request.data.get("refresh"))
        return Response(
            {"detail": "Sesión cerrada."}, status=status.HTTP_200_OK
        )


@extend_schema(tags=["auth"])
class MeView(APIView):
    """Read or edit the authenticated user's own profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer}, summary="Ver mi perfil")
    def get(self, request):
        return Response(
            UserSerializer(request.user, context={"request": request}).data
        )

    @extend_schema(
        request=ProfileUpdateSerializer,
        responses={200: UserSerializer},
        summary="Editar mi perfil",
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = services.update_profile(
            request.user, **serializer.validated_data
        )
        return Response(
            UserSerializer(user, context={"request": request}).data
        )


@extend_schema(tags=["auth"])
class ChangePasswordView(APIView):
    """Change the authenticated user's own password (HU-3)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Contraseña actualizada.")
        },
        summary="Cambiar mi contraseña",
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        services.change_password(
            request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response(
            {"detail": "Contraseña actualizada."}, status=status.HTTP_200_OK
        )


@extend_schema(tags=["users"])
class UserAdminViewSet(viewsets.ModelViewSet):
    """Superadmin-only user CRUD with role management."""

    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsSuperAdmin]

    def perform_create(self, serializer):
        serializer.instance = services.admin_create_user(
            **serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = services.admin_update_user(
            serializer.instance, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        # Baja lógica (HU-1): deactivate instead of hard-deleting.
        services.deactivate_user(instance)

    @extend_schema(
        request=None,
        responses={200: AdminUserSerializer},
        summary="Reactivar un usuario dado de baja",
    )
    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        user = services.reactivate_user(self.get_object())
        return Response(
            AdminUserSerializer(user, context={"request": request}).data
        )
