"""
Tour photos.   Owner: Aitore (Application & Development)

Public
  GET    /api/photos/<id>                       the image itself (cached; a photo is never changed, only replaced)
Staff (manager / admin), every write goes to audit_log
  GET    /api/admin/tours/<id>/photos           list, cover first
  POST   /api/admin/tours/<id>/photos           multipart: file (+ caption, credit) -> added at the end
  POST   /api/admin/tours/<id>/photos/order     {"ids": [3, 1, 2]} -> new order, first = cover
  PATCH  /api/admin/photos/<id>                 {"caption", "credit"}
  DELETE /api/admin/photos/<id>                 row + file

Rules: JPEG / PNG / WebP only, checked by the file's first bytes (not by its name or the browser's word);
max 5 MB; max 10 photos per tour. The stored file name is random, so a user cannot pick a path.
"""
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.audit import audit
from core.exceptions import ApiError
from core.permissions import role_required

from .models import TourPhoto, TourPackage

STAFF = [role_required("manager", "admin")]
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class TourPhotoSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = TourPhoto
        fields = ["id", "url", "caption", "credit", "sort_order"]
        read_only_fields = ["id", "url", "sort_order"]


def sniff_image_type(head: bytes) -> str | None:
    """Real type from the magic bytes. A renamed .exe or an SVG with script is rejected."""
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _photo_error(code, message, field="file", status_code=400):
    return ApiError(code, f"errors.photo.{code}", message, status_code,
                    field_errors={field: [{"message_key": f"errors.photo.{code}", "message": message}]})


def _snapshot(p):
    return {"package": p.package_id, "file": p.file.name, "caption": p.caption, "credit": p.credit, "sort_order": p.sort_order}


def add_photo(package, data: bytes, caption="", credit="", user=None) -> TourPhoto:
    """Validate + store one photo at the end of the package's list. Used by the API and by seed_demo."""
    if len(data) > settings.TOUR_PHOTO_MAX_BYTES:
        raise _photo_error("too_large", "The photo is larger than 5 MB.")
    ctype = sniff_image_type(data[:16])
    if ctype is None:
        raise _photo_error("bad_type", "Only JPEG, PNG or WebP photos can be uploaded.")
    with transaction.atomic():
        TourPackage.objects.select_for_update().get(pk=package.pk)      # serialise uploads to the same tour
        if TourPhoto.objects.filter(package=package).count() >= settings.TOUR_PHOTO_MAX_PER_TOUR:
            raise _photo_error("too_many", f"A tour can have at most {settings.TOUR_PHOTO_MAX_PER_TOUR} photos.", status_code=409)
        last = TourPhoto.objects.filter(package=package).aggregate(m=Max("sort_order"))["m"]
        photo = TourPhoto(package=package, content_type=ctype, caption=caption[:200], credit=credit[:300],
                          sort_order=0 if last is None else last + 1)
        photo.file.save(f"{uuid.uuid4().hex}.{EXTENSIONS[ctype]}", ContentFile(data), save=False)
        try:
            photo.save()
            audit(user, "create", "tour_photos", photo.pk, None, _snapshot(photo))
        except Exception:
            photo.file.delete(save=False)            # do not leave an orphan file if the row failed
            raise
    return photo


# ---------------- public ----------------
class PhotoFileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={(200, "image/*"): bytes})
    def get(self, request, pk):
        photo = get_object_or_404(TourPhoto.objects.select_related("package"), pk=pk)
        if not photo.package.is_active:
            raise Http404
        try:
            fh = photo.file.open("rb")
        except FileNotFoundError:
            raise Http404
        resp = FileResponse(fh, content_type=photo.content_type)
        resp["Cache-Control"] = "public, max-age=86400"
        resp["X-Content-Type-Options"] = "nosniff"
        return resp


# ---------------- staff ----------------
class AdminTourPhotos(APIView):
    permission_classes = STAFF
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):
        package = get_object_or_404(TourPackage, pk=pk)
        return Response(TourPhotoSerializer(package.photos.order_by("sort_order", "id"), many=True).data)

    @extend_schema(request={"multipart/form-data": {"type": "object", "properties": {
        "file": {"type": "string", "format": "binary"}, "caption": {"type": "string"}, "credit": {"type": "string"}}}},
        responses={201: TourPhotoSerializer})
    def post(self, request, pk):
        package = get_object_or_404(TourPackage, pk=pk)
        upload = request.FILES.get("file")
        if upload is None:
            raise _photo_error("required", "Choose a photo to upload.")
        if upload.size > settings.TOUR_PHOTO_MAX_BYTES:        # check before reading it into memory
            raise _photo_error("too_large", "The photo is larger than 5 MB.")
        photo = add_photo(package, upload.read(), request.data.get("caption", ""), request.data.get("credit", ""), request.user)
        return Response(TourPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)


class AdminTourPhotoOrder(APIView):
    permission_classes = STAFF
    parser_classes = [JSONParser]

    @extend_schema(request={"application/json": {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "integer"}}}}},
                   responses={200: TourPhotoSerializer(many=True)})
    def post(self, request, pk):
        package = get_object_or_404(TourPackage, pk=pk)
        ids = request.data.get("ids")
        with transaction.atomic():
            photos = {p.pk: p for p in TourPhoto.objects.select_for_update().filter(package=package)}
            if not isinstance(ids, list) or sorted(map(str, ids)) != sorted(map(str, photos)) or len(set(ids)) != len(ids):
                raise _photo_error("bad_order", "Send every photo id of this tour exactly once.", field="ids")
            old = [p.pk for p in sorted(photos.values(), key=lambda p: (p.sort_order, p.pk))]
            for n, pid in enumerate(ids):
                p = photos[int(pid)]
                if p.sort_order != n:
                    p.sort_order = n
                    p.save(update_fields=["sort_order"])
            audit(request.user, "reorder", "tour_photos", package.pk, {"ids": old}, {"ids": [int(i) for i in ids]})
        return Response(TourPhotoSerializer(package.photos.order_by("sort_order", "id"), many=True).data)


class AdminPhotoDetail(APIView):
    permission_classes = STAFF
    parser_classes = [JSONParser]

    @extend_schema(request=TourPhotoSerializer, responses={200: TourPhotoSerializer})
    def patch(self, request, pk):
        with transaction.atomic():
            photo = get_object_or_404(TourPhoto.objects.select_for_update(), pk=pk)
            old = _snapshot(photo)
            ser = TourPhotoSerializer(photo, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            audit(request.user, "update", "tour_photos", photo.pk, old, _snapshot(photo))
        return Response(ser.data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        with transaction.atomic():
            photo = get_object_or_404(TourPhoto.objects.select_for_update(), pk=pk)
            old, name, package_id = _snapshot(photo), photo.file.name, photo.package_id
            photo.delete()
            # close the gap so the order stays 0..n-1 and the next photo becomes the cover
            for n, p in enumerate(TourPhoto.objects.select_for_update().filter(package_id=package_id).order_by("sort_order", "id")):
                if p.sort_order != n:
                    p.sort_order = n
                    p.save(update_fields=["sort_order"])
            audit(request.user, "delete", "tour_photos", pk, old, None)
            storage = TourPhoto._meta.get_field("file").storage
            transaction.on_commit(lambda: storage.delete(name))     # remove the file only once the row is really gone
        return Response(status=status.HTTP_204_NO_CONTENT)
