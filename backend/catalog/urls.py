from django.urls import path

from .views import DestinationListView, TourDetailView, TourListView

urlpatterns = [
    path("destinations", DestinationListView.as_view()),
    path("tours", TourListView.as_view()),
    path("tours/<int:pk>", TourDetailView.as_view()),
]
