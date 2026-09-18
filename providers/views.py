from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from providers.services import (
    ProviderCategoryNotFound,
    ProviderNotFound,
    UnsupportedProviderQueryParams,
    get_provider_detail,
    list_my_providers,
    list_providers,
    update_my_provider_business,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def provider_list(request):
    try:
        return Response(list_providers(query_params=request.query_params, request=request))
    except UnsupportedProviderQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ProviderCategoryNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_provider_list(request):
    try:
        return Response(
            list_my_providers(query_params=request.query_params, request=request)
        )
    except UnsupportedProviderQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def my_provider_business_detail(request, provider_id):
    try:
        return Response(
            update_my_provider_business(
                provider_id=provider_id,
                data=request.data,
                request=request,
                partial=request.method == "PATCH",
            )
        )
    except ProviderNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def provider_detail(request, slug):
    try:
        return Response(get_provider_detail(slug=slug, request=request))
    except ProviderNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
