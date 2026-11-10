"""
Governance rule (Task 7): every change to important data is written to audit_log.
Owner: Amina A. (Architecture & Security)
"""
from .models import AuditLog


def audit(user, action, table_name, record_id, old=None, new=None):
    """Write one audit row. user=None means "the system" (nightly job, seed ...)."""
    AuditLog.objects.create(
        user=user if (user is not None and getattr(user, "is_authenticated", False)) else None,
        action=action, table_name=table_name, record_id=record_id, old_value=old, new_value=new)
