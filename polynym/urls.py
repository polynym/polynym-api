from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from identity.serializers import PolynymTokenObtainPairSerializer


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "api/token/",
        TokenObtainPairView.as_view(
            serializer_class=PolynymTokenObtainPairSerializer
        ),
        name="token_obtain_pair",
    ),
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path("", include("identity.urls")),
]