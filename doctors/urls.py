from django.urls import path

from doctors import views


app_name = "doctors"

urlpatterns = [
    path(
        "providers/my/<uuid:provider_id>/doctors/",
        views.my_provider_doctor_list,
        name="my-provider-doctor-list",
    ),
    path(
        "providers/my/<uuid:provider_id>/doctors/<uuid:doctor_id>/",
        views.my_provider_doctor_detail,
        name="my-provider-doctor-detail",
    ),
    path(
        "providers/<slug:provider_slug>/doctors/",
        views.provider_doctor_list,
        name="provider-doctor-list",
    ),
    path(
        "doctors/specialties/",
        views.doctor_specialty_list,
        name="doctor-specialty-list",
    ),
    path(
        "doctors/nearby-available/",
        views.nearby_available_doctor_list,
        name="nearby-available-doctor-list",
    ),
    path("doctors/", views.doctor_list, name="doctor-list"),
    path("doctors/<slug:slug>/", views.doctor_detail, name="doctor-detail"),
]
