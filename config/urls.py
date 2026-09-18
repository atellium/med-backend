from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "MedNearby Administration"
admin.site.site_title = "MedNearby Admin"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path("api/", include("core.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("locations.urls")),
    path("api/", include("providers.urls")),
    path("api/", include("doctors.urls")),
    path("admin/", admin.site.urls),
]
