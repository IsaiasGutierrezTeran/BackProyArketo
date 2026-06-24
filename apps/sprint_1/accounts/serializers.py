"""Serializers (I/O only) for registration, profile and admin user management."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.utils import absolute_media_url

from .validators import validate_phone, validate_user_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user (no password)."""

    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "avatar",
            "subscription_plan",
            "is_active",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "role",
            "subscription_plan",
            "is_active",
            "date_joined",
        ]

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class RegisterSerializer(serializers.ModelSerializer):
    """Validates self-registration input. Creation happens in the service layer."""

    password = serializers.CharField(
        write_only=True, validators=[validate_user_password]
    )
    phone = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_phone]
    )
    # El usuario elige su rol al registrarse (superadmin nunca es opción).
    role = serializers.ChoiceField(
        choices=["cliente", "arquitecto", "ingeniero"],
        required=False,
        default="cliente",
    )

    class Meta:
        model = User
        fields = ["email", "full_name", "phone", "password", "role"]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Edit own profile (full_name, phone, avatar, email). HU-3."""

    full_name = serializers.CharField(required=False, allow_blank=False)
    phone = serializers.CharField(
        required=False, allow_blank=True, validators=[validate_phone]
    )
    email = serializers.EmailField(required=False)

    class Meta:
        model = User
        fields = ["full_name", "phone", "avatar", "email"]

    def validate_email(self, value):
        user = self.context["request"].user
        if (
            User.objects.filter(email__iexact=value)
            .exclude(pk=user.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "Ya existe una cuenta con ese correo."
            )
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Self password change: verify current, validate + set new (HU-3)."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, validators=[validate_user_password]
    )

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(
                "La contraseña actual no es correcta."
            )
        return value


class AdminUserSerializer(serializers.ModelSerializer):
    """Superadmin CRUD: can set role and (re)set a password."""

    password = serializers.CharField(
        write_only=True, required=False, validators=[validate_user_password]
    )
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "is_active",
            "password",
            "avatar",
            "subscription_plan",
            "date_joined",
        ]
        read_only_fields = ["id", "date_joined", "avatar"]

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login that also embeds role/email claims and returns the user payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data
