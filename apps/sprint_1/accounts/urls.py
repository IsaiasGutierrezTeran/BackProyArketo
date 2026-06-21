"""Auth routes, mounted under /api/auth/."""

from __future__ import annotations

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", MeView.as_view(), name="me"),
    path("change-password", ChangePasswordView.as_view(), name="change_password"),
]
