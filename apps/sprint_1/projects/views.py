"""Project endpoints: owner-scoped CRUD + dashboard. Views orchestrate only."""

from __future__ import annotations

from datetime import timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.exceptions import ApiException
from core.permissions import IsOwnerOrReadOnly

from . import services
from .models import Comment, ProjectMembership
from .serializers import (
    AssignableUserSerializer,
    CommentSerializer,
    DashboardSerializer,
    InvitationSerializer,
    InviteMemberSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    SyncSerializer,
)


@extend_schema(tags=["projects"])
class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD over the caller's own projects (superadmin sees all)."""

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        # `getattr` keeps drf-spectacular schema generation (AnonymousUser) safe.
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return services.projects_for(user).none()
        return services.projects_for(user)

    def perform_create(self, serializer):
        serializer.instance = services.create_project(
            owner=self.request.user, **serializer.validated_data
        )

    @extend_schema(responses=DashboardSerializer, summary="Resumen del dashboard (CU16)")
    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        summary = services.dashboard_summary(request.user)
        data = DashboardSerializer(summary, context={"request": request}).data
        return Response(data)

    @extend_schema(
        parameters=[OpenApiParameter(
            name="since", type=str, location=OpenApiParameter.QUERY, required=False,
            description="Marca ISO-8601; devuelve solo proyectos modificados después. "
                        "Omite en la primera sincronización.",
        )],
        responses=SyncSerializer,
        summary="Sincronización incremental offline/móvil (CU16)",
    )
    @action(detail=False, methods=["get"])
    def sync(self, request):
        since_raw = request.query_params.get("since")
        since = parse_datetime(since_raw) if since_raw else None
        if since_raw and since is None:
            raise ApiException(
                "Parámetro 'since' inválido (usa ISO-8601, p.ej. 2026-06-14T10:00:00Z).",
                code="bad_request", status_code=400,
            )
        if since is not None and timezone.is_naive(since):
            since = timezone.make_aware(since, dt_timezone.utc)
        data = services.sync_changes(request.user, since)
        return Response(SyncSerializer(data, context={"request": request}).data)

    @extend_schema(summary="Listar colaboradores / invitar (elige usuario por id) (CU14)")
    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        project = self.get_object()
        if request.method == "POST":
            data = InviteMemberSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            membership = services.invite_member(
                owner=request.user, project_id=project.id,
                user_id=data.validated_data["user"], role=data.validated_data["role"],
            )
            return Response(
                ProjectMembershipSerializer(membership).data, status=status.HTTP_201_CREATED
            )
        memberships = project.memberships.select_related("user")
        return Response(ProjectMembershipSerializer(memberships, many=True).data)

    @extend_schema(responses={200: AssignableUserSerializer(many=True)},
                   summary="Usuarios que se pueden invitar a este proyecto (para el selector)")
    @action(detail=True, methods=["get"])
    def assignable(self, request, pk=None):
        self.get_object()  # 404/permiso si no es accesible
        users = services.assignable_users(user=request.user, project_id=pk)
        return Response(AssignableUserSerializer(users, many=True).data)

    @extend_schema(summary="Quitar un colaborador (CU14)")
    @action(detail=True, methods=["delete"], url_path="members/(?P<membership_id>[^/.]+)")
    def remove_member(self, request, pk=None, membership_id=None):
        project = self.get_object()
        services.remove_member(
            owner=request.user, project_id=project.id, membership_id=membership_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["projects"])
class CommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Comments on projects the user can access (CU14). Filter with ?project=<id>."""

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return Comment.objects.none()
        qs = Comment.objects.filter(
            project__in=services.projects_for(user)
        ).select_related("author")
        project = self.request.query_params.get("project")
        return qs.filter(project=project) if project else qs

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not services.projects_for(self.request.user).filter(pk=project.pk).exists():
            raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        if not (instance.author_id == self.request.user.id
                or instance.project.owner_id == self.request.user.id
                or getattr(self.request.user, "is_superadmin", False)):
            raise ApiException("No puedes borrar este comentario.", code="forbidden", status_code=403)
        instance.delete()


@extend_schema(tags=["projects"])
class InvitationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The invited user's inbox: list pending invitations, accept or decline (CU14)."""

    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return ProjectMembership.objects.none()
        return services.pending_invitations_for(user)

    @extend_schema(request=None, responses={200: InvitationSerializer},
                   summary="Aceptar una invitación a colaborar")
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        membership = services.accept_invitation(user=request.user, membership_id=pk)
        return Response(InvitationSerializer(membership, context={"request": request}).data)

    @extend_schema(request=None, responses={204: None},
                   summary="Rechazar una invitación a colaborar")
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        services.decline_invitation(user=request.user, membership_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
