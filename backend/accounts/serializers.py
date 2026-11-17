"""Auth serializers. Owner: Aitore (auth screens/API) with Amina A. (password rules)."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    preferred_language = serializers.ChoiceField(choices=["en", "ru", "kk"], default="en")

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.", code="unique")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)    # min 8, not common, not numeric-only (settings.py)
        except DjangoValidationError as exc:
            # keep Django's error codes (password_too_short ...) so the frontend can translate them
            raise serializers.ValidationError([
                serializers.ErrorDetail(m.message % (m.params or {}), code=m.code) for m in exc.error_list
            ])
        return value

    def create(self, validated):
        return User.objects.create_user(role="tourist", **validated)


class UserSerializer(serializers.ModelSerializer):
    """What the frontend may see about the logged-in user (never the hash or MFA secret)."""
    role = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "role", "preferred_language", "mfa_enabled", "created_at"]
        read_only_fields = ["id", "email", "role", "mfa_enabled", "created_at"]
