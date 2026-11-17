from django.urls import path

from . import views as v

urlpatterns = [
    path("bookings/flex-state", v.FlexStateView.as_view()),
    path("bookings/<int:pk>/cancel-preview", v.CancelPreviewView.as_view()),
    path("bookings/<int:pk>/cancel", v.CancelView.as_view()),
    path("bookings/<int:pk>/undo-cancel", v.UndoCancelView.as_view()),
    path("bookings/<int:pk>/timeline", v.TimelineView.as_view()),
    path("bookings/<int:pk>/handover", v.HandoverCreateView.as_view()),
    path("handovers/incoming", v.IncomingHandoversView.as_view()),
    path("handovers/outgoing", v.OutgoingHandoversView.as_view()),
    path("handovers/<int:pk>/accept", v.AcceptHandoverView.as_view()),
    path("handovers/<int:pk>/decline", v.DeclineHandoverView.as_view()),
    path("handovers/<int:pk>/withdraw", v.WithdrawHandoverView.as_view()),
    path("admin/audit-log/integrity", v.AuditIntegrityView.as_view()),
]
