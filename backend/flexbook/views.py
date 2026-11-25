"""
FlexBook endpoints.   Owner: Amina A. (Architecture & Security)

Tourist (role "tourist" only, server-enforced; someone else's booking -> 404):
  GET  /api/bookings/flex-state             what each of my upcoming bookings can do right now
  GET  /api/bookings/{id}/cancel-preview    "what happens if I cancel?"
  POST /api/bookings/{id}/cancel            cancel (up to 3 days before start)
  POST /api/bookings/{id}/undo-cancel       change of mind within 10 minutes
  GET  /api/bookings/{id}/timeline          the full story of my booking (feature U5)
  POST /api/bookings/{id}/handover          offer my seat to a friend by e-mail
  GET  /api/handovers/incoming | outgoing   open offers to me / from me
  POST /api/handovers/{id}/accept | decline | withdraw
Admin only:
  GET  /api/admin/audit-log/integrity       is the audit log still untouched? (feature U1)
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import AuditLog, Booking, Payment
from bookings.serializers import BookingSerializer
from core.lang import pick_translation, request_lang
from core.permissions import role_required

from . import services
from .models import SeatTransfer
from .sealing import verify_chain

tourist = role_required("tourist")


def _booking_json(booking, request):
    booking = (Booking.objects.select_related("departure__guide__user", "departure__package")
               .prefetch_related("departure__package__translations").get(pk=booking.pk))
    return BookingSerializer(booking, context={"lang": request_lang(request)}).data


# ---------------------------------------------------------------------------------------- cancellation
class CancelPreviewView(APIView):
    permission_classes = [tourist]

    @extend_schema(responses={200: dict})
    def get(self, request, pk):
        p = services.cancel_preview(request.user, pk)
        return Response({**p, "deadline": p["deadline"].isoformat()})


class CancelView(APIView):
    permission_classes = [tourist]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, pk):
        booking, undo_until = services.cancel_booking(request.user, pk)
        return Response({"message_key": "cancel.done", "undo_until": undo_until.isoformat(),
                         "booking": _booking_json(booking, request)})


class UndoCancelView(APIView):
    permission_classes = [tourist]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, pk):
        booking = services.undo_cancel(request.user, pk)
        return Response({"message_key": "cancel.undone", "booking": _booking_json(booking, request)})


class FlexStateView(APIView):
    """One call that tells the screen which buttons to show, so the frontend never has to re-implement the rules."""
    permission_classes = [tourist]

    @extend_schema(responses={200: dict})
    def get(self, request):
        now = timezone.now()
        user = request.user
        bookings = list(Booking.objects.filter(user=user, departure__start_at__gt=now,
                                               status__in=[*Booking.ACTIVE, Booking.CANCELLED])
                        .select_related("departure").order_by("departure__start_at")[:100])
        cancelled_ids = [b.pk for b in bookings if b.status == Booking.CANCELLED]
        last_audit = {}
        if cancelled_ids:
            for a in AuditLog.objects.filter(table_name="bookings", record_id__in=cancelled_ids).order_by("-id"):
                last_audit.setdefault(a.record_id, a)
        offers = {t.booking_id: t for t in SeatTransfer.objects.filter(
            booking__in=[b.pk for b in bookings], status=SeatTransfer.PENDING, expires_at__gt=now)}
        out = []
        for b in bookings:
            deadline = services.cancel_deadline(b.departure)
            active = b.status in Booking.ACTIVE
            undo_until = None
            a = last_audit.get(b.pk)
            if b.status == Booking.CANCELLED and a and a.action == "cancel" and a.user_id == user.pk:
                raw = (a.new_value or {}).get("undo_until")
                if raw and raw > now.isoformat():
                    undo_until = raw
            offer = offers.get(b.pk)
            out.append({
                "booking_id": b.pk,
                "can_cancel": active and now <= deadline,
                "cancel_deadline": deadline.isoformat(),
                "can_undo": undo_until is not None, "undo_until": undo_until,
                "can_handover": active and offer is None,
                "handover": {"id": offer.pk, "to_email": offer.to_email, "expires_at": offer.expires_at.isoformat()} if offer else None,
            })
        return Response(out)


# ---------------------------------------------------------------------------------------- timeline (U5)
_STATUS_EVENT = {"Confirmed": "confirmed", "Completed": "completed", "Expired": "expired"}


class TimelineView(APIView):
    """
    The tourist sees the same facts the audit log keeps - in plain words and in their language.
    Other people's names, e-mails and phone numbers are never shown: only "you", "the system" or "staff".
    """
    permission_classes = [tourist]

    @extend_schema(responses={200: dict})
    def get(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        # A booking handed over to somebody else must stay readable for the NEW owner only.
        if booking.user_id != request.user.pk:
            return Response({"code": "not_found", "message_key": "errors.not_found", "message": "Not found.",
                             "field_errors": {}}, status=404)
        payment_ids = list(Payment.objects.filter(booking=booking).values_list("pk", flat=True))
        rows = (AuditLog.objects.filter(Q(table_name="bookings", record_id=booking.pk)
                                        | Q(table_name="payments", record_id__in=payment_ids))
                .select_related("user__role").order_by("created_at", "id"))
        events = []
        for a in rows:
            who = "system" if a.user is None else ("you" if a.user_id == request.user.pk else
                                                  ("staff" if a.user.role.name in ("manager", "admin") else "other"))
            new = a.new_value or {}
            if a.action == "status_change":
                kind = _STATUS_EVENT.get(new.get("status", ""), "status_changed")
            else:
                kind = {"create": "created", "payment_failed": "payment_failed", "cancel": "cancelled",
                        "cancel_undo": "cancel_undone", "expire": "expired", "handover_offer": "handover_offered",
                        "handover": "handed_over", "handover_declined": "handover_declined",
                        "handover_withdrawn": "handover_withdrawn", "handover_expired": "handover_expired",
                        "seed": "created"}.get(a.action, "other")
            events.append({"at": a.created_at, "kind": kind, "by": who,
                           "details": {k: v for k, v in new.items()
                                       if k in ("status", "travelers", "total_cost", "seats_returned", "undo_until", "reason")}})
        return Response({"booking_id": booking.pk, "booking_ref": booking.booking_ref, "events": events})


# ---------------------------------------------------------------------------------------- handover (U4)
class HandoverCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    message = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")


class HandoverCreateView(APIView):
    permission_classes = [tourist]

    @extend_schema(request=HandoverCreateSerializer, responses={201: dict})
    def post(self, request, pk):
        ser = HandoverCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        t = services.initiate_handover(request.user, pk, ser.validated_data["email"], ser.validated_data["message"])
        # Same answer whether or not that e-mail has an account (no way to probe for registered users).
        return Response({"message_key": "handover.sent", "id": t.pk, "expires_at": t.expires_at.isoformat()}, status=201)


class IncomingHandoversView(APIView):
    permission_classes = [tourist]

    @extend_schema(responses={200: dict})
    def get(self, request):
        lang = request_lang(request)
        qs = (SeatTransfer.objects.filter(to_email__iexact=request.user.email, status=SeatTransfer.PENDING,
                                          expires_at__gt=timezone.now())
              .select_related("from_user", "booking__departure__package")
              .prefetch_related("booking__departure__package__translations").order_by("expires_at"))
        out = []
        for t in qs:
            tr = pick_translation(t.booking.departure.package.translations.all(), lang)
            out.append({"id": t.pk, "from_name": t.from_user.full_name, "message": t.message,
                        "booking_ref": t.booking.booking_ref, "package_id": t.booking.departure.package_id,
                        "package_title": tr.title if tr else f"#{t.booking.departure.package_id}",
                        "start_at": t.booking.departure.start_at, "travelers_count": t.booking.travelers_count,
                        "total_cost": str(t.booking.total_cost), "booking_status": t.booking.status,
                        "expires_at": t.expires_at})
        return Response(out)


class OutgoingHandoversView(APIView):
    permission_classes = [tourist]

    @extend_schema(responses={200: dict})
    def get(self, request):
        qs = SeatTransfer.objects.filter(from_user=request.user, status=SeatTransfer.PENDING,
                                         expires_at__gt=timezone.now()).select_related("booking").order_by("expires_at")
        return Response([{"id": t.pk, "booking_id": t.booking_id, "booking_ref": t.booking.booking_ref,
                          "to_email": t.to_email, "expires_at": t.expires_at} for t in qs])


class _HandoverAction(APIView):
    """accept / decline / withdraw share one shape. NB: do not call the attribute `action` - DRF reserves it."""
    permission_classes = [tourist]
    handler = None

    def reply(self, result, request):
        raise NotImplementedError

    @extend_schema(request=None, responses={200: dict})
    def post(self, request, pk):
        return Response(self.reply(type(self).handler(request.user, pk), request))


class AcceptHandoverView(_HandoverAction):
    handler = staticmethod(services.accept_handover)

    def reply(self, booking, request):
        return {"message_key": "handover.accepted", "booking": _booking_json(booking, request)}


class DeclineHandoverView(_HandoverAction):
    handler = staticmethod(services.decline_handover)

    def reply(self, t, request):
        return {"message_key": "handover.declined"}


class WithdrawHandoverView(_HandoverAction):
    handler = staticmethod(services.withdraw_handover)

    def reply(self, t, request):
        return {"message_key": "handover.withdrawn"}


# ---------------------------------------------------------------------------------------- audit integrity (U1)
class AuditIntegrityView(APIView):
    """READ-ONLY. Re-computes every hash; nothing is written."""
    permission_classes = [role_required("admin")]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({**verify_chain(), "checked_at": timezone.now()})
