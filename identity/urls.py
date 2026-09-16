from django.urls import path

from .views import (
    IdentityDetailView,
    PersonErasureView,
    PersonIdentityCollectionView,
    PersonIdentityDetailView,
    demo_page,
)

urlpatterns = [
    path("demo/", demo_page, name="demo-page"),
    path(
        "api/persons/<int:person_id>/identity/",
        PersonIdentityDetailView.as_view(),
        name="person-identity-detail",
    ),
    path(
        "api/persons/<int:person_id>/identities/",
        PersonIdentityCollectionView.as_view(),
        name="person-identity-collection",
    ),
    path(
        "api/identities/<int:identity_id>/",
        IdentityDetailView.as_view(),
        name="identity-detail",
    ),
    path(
        "api/persons/<int:person_id>/",
        PersonErasureView.as_view(),
        name="person-erasure",
    ),
]
