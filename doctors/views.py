from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from doctors.services import (
    DoctorNotFound,
    DoctorSpecialtyNotFound,
    ProviderNotFound,
    UnsupportedDoctorQueryParams,
    add_doctor_for_my_provider,
    delete_doctor_for_my_provider,
    get_doctor_detail,
    list_doctor_specialties,
    list_nearby_available_doctors,
    list_provider_doctors,
    list_doctors,
    update_doctor_for_my_provider,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_list(request):
    try:
        return Response(list_doctors(query_params=request.query_params, request=request))
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except DoctorSpecialtyNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby_available_doctor_list(request):
    try:
        return Response(
            list_nearby_available_doctors(
                query_params=request.query_params,
                request=request,
            )
        )
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_specialty_list(request):
    try:
        return Response(
            list_doctor_specialties(
                query_params=request.query_params,
                request=request,
            )
        )
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def provider_doctor_list(request, provider_slug):
    try:
        return Response(
            list_provider_doctors(
                provider_slug=provider_slug,
                query_params=request.query_params,
                request=request,
            )
        )
    except UnsupportedDoctorQueryParams as error:
        return Response(
            {"detail": str(error)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ProviderNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def my_provider_doctor_list(request, provider_id):
    try:
        return Response(
            add_doctor_for_my_provider(
                provider_id=provider_id,
                data=request.data,
                request=request,
            ),
            status=status.HTTP_201_CREATED,
        )
    except ProviderNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def my_provider_doctor_detail(request, provider_id, doctor_id):
    try:
        if request.method == "DELETE":
            delete_doctor_for_my_provider(
                provider_id=provider_id,
                doctor_id=doctor_id,
                request=request,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            update_doctor_for_my_provider(
                provider_id=provider_id,
                doctor_id=doctor_id,
                data=request.data,
                request=request,
                partial=request.method == "PATCH",
            )
        )
    except DoctorNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def doctor_detail(request, slug):
    try:
        return Response(get_doctor_detail(slug=slug, request=request))
    except DoctorNotFound as error:
        return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
