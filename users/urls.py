from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import MeView, RegisterView

urlpatterns = [
    # POST /api/auth/register/  — create account
    path("register/", RegisterView.as_view(), name="auth-register"),

    # POST /api/auth/token/     — obtain access + refresh tokens
    path("token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),

    # POST /api/auth/token/refresh/ — refresh access token
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # GET  /api/auth/me/        — current user profile
    path("me/", MeView.as_view(), name="auth-me"),
]
