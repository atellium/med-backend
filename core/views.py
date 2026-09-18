from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from doctors.models import DoctorSpecialty
from providers.models import ProviderCategory


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def readiness(request):
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        pass
    try:
        cache_key = "health:readiness"
        cache.set(cache_key, "ok", timeout=10)
        checks["cache"] = cache.get(cache_key) == "ok"
    except Exception:
        pass
    ready = all(checks.values())
    return Response(
        {"status": "ok" if ready else "unavailable", "checks": checks},
        status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def search(request):
    query = request.query_params.get("q", "").strip()
    provider_categories = ProviderCategory.objects.filter(is_active=True)
    doctor_specialties = DoctorSpecialty.objects.filter(is_active=True)

    if query:
        lookup = (
            Q(name__icontains=query)
            | Q(label__icontains=query)
            | Q(slug__icontains=query)
            | Q(aliases__icontains=query)
        )
        provider_categories = provider_categories.filter(lookup)
        doctor_specialties = doctor_specialties.filter(lookup)

    results = [
        _search_item(provider_category, "provider_category")
        for provider_category in provider_categories.order_by("sort_order", "name")
    ]
    results.extend(
        _search_item(doctor_specialty, "doctor_specialty")
        for doctor_specialty in doctor_specialties.order_by("sort_order", "name")
    )

    return Response(results)


def _search_item(item, item_type):
    return {
        "id": item.id,
        "name": item.name,
        "label": item.label,
        "slug": item.slug,
        "aliases": item.aliases,
        "type": item_type,
    }
