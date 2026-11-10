from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, MeView, MfaVerifyView, RegisterView

urlpatterns = [
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/mfa/verify", MfaVerifyView.as_view()),
    path("auth/refresh", TokenRefreshView.as_view()),
    path("me", MeView.as_view()),
]
