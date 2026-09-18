from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from django.utils import timezone

from providers.models import Provider, ProviderCategory
from providers.serializers import (
    MyProviderListQuerySerializer,
    ProviderBusinessUpdateSerializer,
    ProviderDetailSerializer,
    ProviderListItemSerializer,
    ProviderListQuerySerializer,
    build_pagination,
)


class UnsupportedProviderQueryParams(ValueError):
    def __init__(self, params):
        self.params = sorted(params)
        super().__init__(
            "Unsupported query parameter(s): "
            f"{', '.join(self.params)}."
        )


class ProviderCategoryNotFound(LookupError):
    pass


class ProviderNotFound(LookupError):
    pass


def list_providers(*, query_params, request):
    unsupported_params = set(query_params) - set(ProviderListQuerySerializer().fields)
    if unsupported_params:
        raise UnsupportedProviderQueryParams(unsupported_params)

    query_serializer = ProviderListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    category = None
    category_key = params.get("category")
    providers = Provider.objects.filter(is_active=True, location__isnull=False)
    if category_key:
        category = find_provider_category(category_key)
        if category is None:
            raise ProviderCategoryNotFound("Provider category was not found.")
        providers = providers.filter(categories=category)

    if "is_verified" in query_params:
        providers = providers.filter(is_verified=params["is_verified"])
    if "is_featured" in query_params:
        providers = providers.filter(is_featured=params["is_featured"])
    if "is_medicine_enquiry" in query_params:
        providers = providers.filter(is_medicine_enquiry=params["is_medicine_enquiry"])
    if "is_test_book" in query_params:
        providers = providers.filter(is_test_book=params["is_test_book"])
    if "open_now" in query_params:
        open_now_filter = _open_now_filter()
        no_business_hours_filter = Q(provider_hours__isnull=True)
        if params["open_now"]:
            providers = providers.filter(open_now_filter | no_business_hours_filter)
        else:
            providers = providers.exclude(open_now_filter).exclude(
                no_business_hours_filter
            )
    providers = providers.distinct()

    user_location = Point(float(params["lng"]), float(params["lat"]), srid=4326)
    providers = (
        providers.filter(
            location__distance_lte=(user_location, D(km=params["radius_km"]))
        )
        .annotate(distance=Distance("location", user_location))
        .select_related("city", "city__state")
        .prefetch_related("categories", "provider_hours")
        .order_by("distance", "-is_featured", "name")
    )

    count = providers.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = providers[offset : offset + page_size]

    response = {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
    }
    if category:
        response["category"] = provider_category_data(category)
    response["results"] = ProviderListItemSerializer(
        page_items,
        many=True,
        context={"request": request},
    ).data
    return response


def list_my_providers(*, query_params, request):
    unsupported_params = set(query_params) - set(MyProviderListQuerySerializer().fields)
    if unsupported_params:
        raise UnsupportedProviderQueryParams(unsupported_params)

    query_serializer = MyProviderListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    providers = (
        Provider.objects.filter(owner=request.user)
        .select_related("city", "city__state")
        .prefetch_related("categories", "provider_hours")
        .order_by("-is_featured", "name")
    )

    count = providers.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = providers[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "results": ProviderListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def update_my_provider_business(*, provider_id, data, request, partial=True):
    provider = (
        Provider.objects.filter(pk=provider_id, owner=request.user)
        .select_related("city", "city__state")
        .prefetch_related("categories", "provider_hours")
        .first()
    )
    if provider is None:
        raise ProviderNotFound("Provider was not found.")

    serializer = ProviderBusinessUpdateSerializer(
        provider,
        data=data,
        partial=partial,
    )
    serializer.is_valid(raise_exception=True)
    provider = serializer.save()

    return ProviderDetailSerializer(provider, context={"request": request}).data


def get_provider_detail(*, slug, request):
    provider = (
        Provider.objects.filter(slug=slug, is_active=True)
        .select_related("city", "city__state")
        .prefetch_related("categories", "provider_hours")
        .first()
    )
    if provider is None:
        raise ProviderNotFound("Provider was not found.")

    return ProviderDetailSerializer(provider, context={"request": request}).data


def find_provider_category(category_key):
    return ProviderCategory.objects.filter(slug=category_key, is_active=True).first()


def provider_category_data(category):
    return {
        "id": category.id,
        "name": category.name,
        "label": category.label,
        "slug": category.slug,
        "aliases": category.aliases,
    }


def _open_now_filter():
    now = timezone.localtime()
    return Q(
        provider_hours__days__contains=[now.weekday()],
        provider_hours__opens_at__lte=now.time(),
        provider_hours__closes_at__gt=now.time(),
    )
