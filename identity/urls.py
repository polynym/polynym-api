from django.urls import path

from .views import PersonIdentityDetailView, demo_page

urlpatterns = [
    path("demo/", demo_page, name="demo-page"),
    path(
        "api/persons/<int:person_id>/identity/",
        PersonIdentityDetailView.as_view(),
        name="person-identity-detail",
    ),
]
