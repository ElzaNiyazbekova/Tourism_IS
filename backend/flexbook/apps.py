"""FlexBook = the "Flexible booking" add-on.   Owner: Amina A. (Architecture & Security)

A separate Django app on purpose: nothing in bookings/ or catalog/ had to be edited.
ready() connects the audit-chain signal (see sealing.py).
"""
from django.apps import AppConfig


class FlexbookConfig(AppConfig):
    name = "flexbook"
    verbose_name = "FlexBook (cancel, undo, handover, tamper-evident audit)"

    def ready(self):
        from . import sealing  # noqa: F401  (registers the post_save receiver)
