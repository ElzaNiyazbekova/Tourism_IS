from django.urls import path

from .favorite_views import FavoriteIdsView, FavoriteItemView, FavoriteListView
from .guide_views import GuideDepartureDetailView, GuideDepartureListView, GuideMeView
from .photos import PhotoFileView
from .views import DestinationListView, GuideProfileView, ReviewCreateView, ReviewDeleteView, TourDetailView, TourListView

urlpatterns = [
    path("destinations", DestinationListView.as_view()),
    path("tours", TourListView.as_view()),
    path("tours/<int:pk>", TourDetailView.as_view()),
    path("tours/<int:pk>/reviews", ReviewCreateView.as_view()),
    path("reviews", ReviewCreateView.as_view()),
    path("reviews/<int:pk>", ReviewDeleteView.as_view()),
    path("guides/<int:pk>", GuideProfileView.as_view()),
    path("photos/<int:pk>", PhotoFileView.as_view()),
    # tourist's favourite tours
    path("favorites", FavoriteListView.as_view()),
    path("favorites/ids", FavoriteIdsView.as_view()),
    path("favorites/<int:package_id>", FavoriteItemView.as_view()),
    # guide cabinet (role "guide" only)
    path("guide/me", GuideMeView.as_view()),
    path("guide/departures", GuideDepartureListView.as_view()),
    path("guide/departures/<int:pk>", GuideDepartureDetailView.as_view()),
]
