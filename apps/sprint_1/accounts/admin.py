from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "full_name"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": ("full_name", "phone", "avatar")}),
        ("Suscripción", {"fields": ("subscription_plan",)}),
        (
            "Rol y permisos",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ["date_joined", "last_login"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
