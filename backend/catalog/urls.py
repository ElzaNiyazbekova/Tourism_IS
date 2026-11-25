from django.urls import path

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
]
