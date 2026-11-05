from django.urls import path

from apps.warehouse.views import (
    AgencyReferenceCollectionView,
    AgencyReferenceDetailView,
    EmployeeReferenceCollectionView,
    EmployeeReferenceDetailView,
    ReferenceDataView,
    SelectableReferenceCollectionView,
    SelectableReferenceDetailView,
)

app_name = "warehouse"

urlpatterns = [
    path("", ReferenceDataView.as_view(), name="reference-data"),
    path("agencies/", AgencyReferenceCollectionView.as_view(), name="reference-agencies"),
    path("agencies/<uuid:pk>/", AgencyReferenceDetailView.as_view(), name="reference-agency"),
    path("employees/", EmployeeReferenceCollectionView.as_view(), name="reference-employees"),
    path(
        "employees/<str:role>/<uuid:pk>/",
        EmployeeReferenceDetailView.as_view(),
        name="reference-employee",
    ),
    path(
        "dimensions/<str:kind>/",
        SelectableReferenceCollectionView.as_view(),
        name="reference-dimension-collection",
    ),
    path(
        "dimensions/<str:kind>/<uuid:pk>/",
        SelectableReferenceDetailView.as_view(),
        name="reference-dimension-detail",
    ),
]
