"""
Favourite tours of a tourist ("♡").   Owner: Aitore (Application & Development)

GET    /api/favorites?lang=          saved tours, newest first (same cards as the catalogue)
GET    /api/favorites/ids            just the package ids -> hearts in the catalogue
PUT    /api/favorites/<package_id>   save (idempotent: 201 first time, 200 if already saved)
DELETE /api/favorites/<package_id>   remove (idempotent: 204)

Role "tourist" only. Deactivated tours disappear from the list but the row is kept (comes back on re-activation).
"""
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ApiError
from core.lang import request_lang
from core.permissions import role_required

from .models import Favorite, TourPackage
from .serializers import TourListSerializer
from .views import base_tour_queryset


class FavoriteListView(generics.ListAPIView):
    permission_classes = [role_required("tourist")]
    serializer_class = TourListSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "lang": request_lang(self.request)}

    @extend_schema(parameters=[OpenApiParameter("lang", str, description="en|ru|kk")])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        saved = Favorite.objects.filter(user=self.request.user, package=OuterRef("pk"))
        return (base_tour_queryset().filter(favorites__user=self.request.user)
                .annotate(saved_at=Subquery(saved.values("created_at")[:1]))
                .order_by("-saved_at", "id"))


class FavoriteIdsView(APIView):
    permission_classes = [role_required("tourist")]

    @extend_schema(responses={200: {"type": "array", "items": {"type": "integer"}}})
    def get(self, request):
        ids = (Favorite.objects.filter(user=request.user, package__is_active=True)
               .order_by("package_id").values_list("package_id", flat=True))
        return Response(list(ids))


class FavoriteItemView(APIView):
    permission_classes = [role_required("tourist")]

    @extend_schema(request=None, responses={200: None, 201: None})
    def put(self, request, package_id):
        if not TourPackage.objects.filter(pk=package_id, is_active=True).exists():
            raise ApiError("not_found", "errors.not_found", "Tour not found.", 404)
        try:
            with transaction.atomic():
                _, created = Favorite.objects.get_or_create(user=request.user, package_id=package_id)
        except IntegrityError:          # two clicks at the same moment: the other request already saved it
            created = False
        return Response({"package_id": package_id, "saved": True},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, package_id):
        Favorite.objects.filter(user=request.user, package_id=package_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
