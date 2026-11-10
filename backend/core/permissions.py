"""
Server-side role enforcement (never trust Angular guards).
Unauthenticated -> 401 (DRF IsAuthenticated), wrong role -> 403.
Owner: Amina A. (Architecture & Security)

Usage in a view:   permission_classes = [IsTourist]      or     [role_required("manager", "admin")]

Role table (what each role may open; evidence = `python manage.py permission_matrix`, docs/ROLE_PERMISSIONS.md):
    tourist  -> own bookings, pay            guide  -> (Phase 3 dashboard)
    analyst  -> aggregate reports ONLY       manager -> tours + departures CRUD + reports
    admin    -> everything a manager can     (+ admin-only endpoints from Phase 3, e.g. audit log)
"""
from rest_framework.permissions import IsAuthenticated


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


# One ready-made permission class per role (and per group of roles). Views import these names,
# so "who may open this endpoint" is readable in one line.
IsTourist = role_required("tourist")
IsGuide = role_required("guide")
IsManager = role_required("manager")
IsAdmin = role_required("admin")
IsAnalyst = role_required("analyst")
IsStaffRole = role_required("manager", "admin")                    # tour/departure management
IsAnalystOrStaff = role_required("analyst", "manager", "admin")    # aggregate reports

for _cls, _name in ((IsTourist, "IsTourist"), (IsGuide, "IsGuide"), (IsManager, "IsManager"), (IsAdmin, "IsAdmin"),
                    (IsAnalyst, "IsAnalyst"), (IsStaffRole, "IsStaffRole"), (IsAnalystOrStaff, "IsAnalystOrStaff")):
    _cls.__name__ = _cls.__qualname__ = _name       # readable names in Swagger / error logs
