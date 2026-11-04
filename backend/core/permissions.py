"""
Server-side role enforcement (never trust Angular guards).
Unauthenticated -> 401 (DRF IsAuthenticated), wrong role -> 403.
Owner: Amina A. (Architecture & Security)

Usage in a view:   permission_classes = [role_required("tourist")]
"""
from rest_framework.permissions import BasePermission, IsAuthenticated


def role_required(*roles):
    """Build a permission class: logged in AND role name in `roles`."""

    class _RolePermission(IsAuthenticated):
        message = "Your role is not allowed to use this endpoint."

        def has_permission(self, request, view):
            if not super().has_permission(request, view):
                return False   # -> 401 because the authenticator provides a WWW-Authenticate header
            return request.user.role.name in roles

    _RolePermission.__name__ = "Role_" + "_".join(roles)
    return _RolePermission


class IsStaffRole(BasePermission):
    """manager or admin (used from Phase 2 on admin endpoints)."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role.name in ("manager", "admin"))
