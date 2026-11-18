from django.urls import path

from .photos import PhotoFileView
from .views import DestinationListView, GuideProfileView, TourDetailView, TourListView

urlpatterns = [
    path("destinations", DestinationListView.as_view()),
    path("tours", TourListView.as_view()),
    path("tours/<int:pk>", TourDetailView.as_view()),
    path("guides/<int:pk>", GuideProfileView.as_view()),
    path("photos/<int:pk>", PhotoFileView.as_view()),
]
