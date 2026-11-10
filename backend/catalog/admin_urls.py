from django.urls import path

from . import admin_views as v

urlpatterns = [
    path("tours", v.AdminTourListCreate.as_view()),
    path("tours/<int:pk>", v.AdminTourDetail.as_view()),
    path("tours/<int:pk>/deactivate", v.TourDeactivate.as_view()),
    path("tours/<int:pk>/activate", v.TourActivate.as_view()),
    path("departures", v.AdminDepartureListCreate.as_view()),
    path("departures/<int:pk>", v.AdminDepartureDetail.as_view()),
    path("departures/<int:pk>/deactivate", v.DepartureDeactivate.as_view()),
    path("departures/<int:pk>/activate", v.DepartureActivate.as_view()),
    path("destinations", v.AdminDestinationList.as_view()),
    path("guides", v.AdminGuideList.as_view()),
]
