from django.urls import path

from providers import views


app_name = "providers"

urlpatterns = [
    path("providers/my/", views.my_provider_list, name="my-provider-list"),
    path(
        "providers/my/<uuid:provider_id>/",
        views.my_provider_business_detail,
        name="my-provider-business-detail",
    ),
    path("providers/", views.provider_list, name="provider-list"),
    path("providers/<slug:slug>/", views.provider_detail, name="provider-detail"),
]
