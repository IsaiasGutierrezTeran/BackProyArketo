"""Reusable, role-aware DRF permissions."""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsSuperAdmin(BasePermission):
    """Only the superadmin role (or a Django superuser)."""

    message = "Se requiere rol de superadministrador."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superadmin", False)
        )


def role_required(*roles: str) -> type[BasePermission]:
    """Build a permission class that allows only the given roles (or superadmin)."""

    allowed = set(roles)

    class _RolePermission(BasePermission):
        message = (
            f"Se requiere uno de los roles: {', '.join(sorted(allowed))}."
        )

        def has_permission(self, request, view) -> bool:
            user = request.user
            if not (user and user.is_authenticated):
                return False
            return (
                getattr(user, "is_superadmin", False)
                or getattr(user, "role", None) in allowed
            )

    return _RolePermission


# Diseñar/modelar (subir plano, detección, editar/importar 3D, diseño IA, boceto)
# es exclusivo del Arquitecto (y superadmin). El cliente delega el diseño.
IsArquitecto = role_required("arquitecto")
IsArquitecto.message = "Solo un Arquitecto puede diseñar o modelar. Invita a un arquitecto al proyecto."


class IsOwnerOrReadOnly(BasePermission):
    """Write only for the object's owner (or superadmin); read for any authed user."""

    owner_field = "owner"

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(
            obj, getattr(view, "owner_field", self.owner_field), None
        )
        return owner == user or getattr(user, "is_superadmin", False)
