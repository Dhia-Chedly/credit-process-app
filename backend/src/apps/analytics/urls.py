from django.urls import path

from apps.analytics.views import (
    ActivityView,
    AgencyComparisonView,
    DelayAndAgingView,
    EmployeeComparisonView,
    MetadataView,
    OverviewView,
    PipelineView,
    ProductsAndRequestsView,
    RejectionView,
)

app_name = "analytics"

urlpatterns = [
    path("metadata/", MetadataView.as_view(), name="metadata"),
    path("overview/", OverviewView.as_view(), name="overview"),
    path("pipeline/", PipelineView.as_view(), name="pipeline"),
    path("agencies/", AgencyComparisonView.as_view(), name="agencies"),
    path("employees/", EmployeeComparisonView.as_view(), name="employees"),
    path("delays/", DelayAndAgingView.as_view(), name="delays"),
    path("rejections/", RejectionView.as_view(), name="rejections"),
    path("activities/", ActivityView.as_view(), name="activities"),
    path("products-requests/", ProductsAndRequestsView.as_view(), name="products-requests"),
]
