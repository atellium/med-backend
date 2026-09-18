from datetime import time

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from django.utils import timezone

from doctors.models import Doctor, DoctorSchedule, DoctorSpecialty
from doctors.serializers import (
    DoctorDetailSerializer,
    DoctorListItemSerializer,
    DoctorListQuerySerializer,
    NearbyAvailableDoctorListQuerySerializer,
    DoctorSpecialtyListItemSerializer,
    DoctorSpecialtyListQuerySerializer,
    DoctorWriteSerializer,
    ProviderDoctorListQuerySerializer,
    doctor_specialty_data,
    next_doctor_schedule_slot,
)
from providers.models import Provider
from providers.serializers import build_pagination


class UnsupportedDoctorQueryParams(ValueError):
    def __init__(self, params):
        self.params = sorted(params)
        super().__init__(
            "Unsupported query parameter(s): "
            f"{', '.join(self.params)}."
        )


class DoctorSpecialtyNotFound(LookupError):
    pass


class DoctorNotFound(LookupError):
    pass


class ProviderNotFound(LookupError):
    pass


NEARBY_AVAILABLE_DOCTOR_RADIUS_KM = 5
NEARBY_AVAILABLE_DOCTOR_LIMIT = 10


def list_doctors(*, query_params, request):
    unsupported_params = set(query_params) - set(DoctorListQuerySerializer().fields)
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = DoctorListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    specialty = find_doctor_specialty(params["specialty"])
    if specialty is None:
        raise DoctorSpecialtyNotFound("Doctor specialty was not found.")

    user_location = Point(float(params["lng"]), float(params["lat"]), srid=4326)
    doctors = (
        Doctor.objects.filter(
            is_active=True,
            provider__is_active=True,
            provider__location__isnull=False,
            specialties=specialty,
        )
        .filter(
            provider__location__distance_lte=(
                user_location,
                D(km=params["radius_km"]),
            )
        )
        .annotate(distance=Distance("provider__location", user_location))
        .select_related("provider", "provider__city")
        .prefetch_related(
            "specialties",
            "schedules",
            "provider__categories",
            "provider__provider_hours",
        )
        .order_by("distance", "-is_featured", "name")
        .distinct()
    )

    if params.get("available_today"):
        doctors = doctors.filter(_available_today_schedule_filter())

    count = doctors.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = doctors[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "specialty": doctor_specialty_data(specialty),
        "results": DoctorListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def list_nearby_available_doctors(*, query_params, request):
    unsupported_params = set(query_params) - set(
        NearbyAvailableDoctorListQuerySerializer().fields
    )
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = NearbyAvailableDoctorListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    now = timezone.localtime()
    user_location = Point(float(params["lng"]), float(params["lat"]), srid=4326)
    doctors = (
        Doctor.objects.filter(
            is_active=True,
            provider__is_active=True,
            provider__location__isnull=False,
        )
        .filter(
            provider__location__distance_lte=(
                user_location,
                D(km=NEARBY_AVAILABLE_DOCTOR_RADIUS_KM),
            )
        )
        .filter(schedules__is_active=True)
        .annotate(distance=Distance("provider__location", user_location))
        .select_related("provider", "provider__city")
        .prefetch_related(
            "specialties",
            "schedules",
            "provider__categories",
            "provider__provider_hours",
        )
        .order_by("distance", "-is_featured", "name")
        .distinct()
    )

    ranked_doctors = []
    for doctor in doctors:
        slot = next_doctor_schedule_slot(doctor.schedules.all(), now=now)
        if slot is None:
            continue

        ranked_doctors.append((doctor, _schedule_slot_sort_key(slot)))

    ranked_doctors.sort(
        key=lambda item: (
            item[1],
            item[0].distance.km if getattr(item[0], "distance", None) else 0,
            not item[0].is_featured,
            item[0].name,
        )
    )
    page_items = [
        doctor
        for doctor, _ in ranked_doctors[:NEARBY_AVAILABLE_DOCTOR_LIMIT]
    ]

    return {
        "results": DoctorListItemSerializer(
            page_items,
            many=True,
            context={"request": request, "now": now},
        ).data,
    }


def list_doctor_specialties(*, query_params, request):
    unsupported_params = set(query_params) - set(
        DoctorSpecialtyListQuerySerializer().fields
    )
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = DoctorSpecialtyListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    specialties = DoctorSpecialty.objects.filter(is_active=True)

    search = params.get("search")
    if search:
        specialties = specialties.filter(
            Q(name__icontains=search)
            | Q(label__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )

    body_part = params.get("body_part")
    if body_part:
        specialties = specialties.filter(body_part=body_part)

    if "is_featured" in params:
        specialties = specialties.filter(is_featured=params["is_featured"])

    specialties = specialties.order_by("sort_order", "name", "pk")
    count = specialties.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = specialties[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "results": DoctorSpecialtyListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def list_provider_doctors(*, provider_slug, query_params, request):
    unsupported_params = set(query_params) - set(
        ProviderDoctorListQuerySerializer().fields
    )
    if unsupported_params:
        raise UnsupportedDoctorQueryParams(unsupported_params)

    query_serializer = ProviderDoctorListQuerySerializer(data=query_params)
    query_serializer.is_valid(raise_exception=True)
    params = query_serializer.validated_data

    provider = Provider.objects.filter(slug=provider_slug, is_active=True).first()
    if provider is None:
        raise ProviderNotFound("Provider was not found.")

    doctors = (
        _doctor_detail_queryset()
        .filter(provider=provider, is_active=True)
        .order_by("-is_featured", "name")
        .distinct()
    )

    if params.get("available_today"):
        doctors = doctors.filter(_available_today_schedule_filter())

    count = doctors.count()
    page = params["page"]
    page_size = params["page_size"]
    offset = (page - 1) * page_size
    page_items = doctors[offset : offset + page_size]

    return {
        "pagination": build_pagination(count=count, page=page, page_size=page_size),
        "provider": {
            "id": provider.id,
            "name": provider.name,
            "slug": provider.slug,
        },
        "results": DoctorListItemSerializer(
            page_items,
            many=True,
            context={"request": request},
        ).data,
    }


def add_doctor_for_my_provider(*, provider_id, data, request):
    provider = Provider.objects.filter(pk=provider_id, owner=request.user).first()
    if provider is None:
        raise ProviderNotFound("Provider was not found.")

    serializer = DoctorWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    doctor = serializer.save(provider=provider)
    doctor = _doctor_detail_queryset().get(pk=doctor.pk)

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def update_doctor_for_my_provider(*, provider_id, doctor_id, data, request, partial=True):
    doctor = (
        _doctor_detail_queryset()
        .filter(
            pk=doctor_id,
            provider_id=provider_id,
            provider__owner=request.user,
        )
        .first()
    )
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    serializer = DoctorWriteSerializer(
        doctor,
        data=data,
        partial=partial,
    )
    serializer.is_valid(raise_exception=True)
    doctor = serializer.save()
    doctor = _doctor_detail_queryset().get(pk=doctor.pk)

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def delete_doctor_for_my_provider(*, provider_id, doctor_id, request):
    doctor = Doctor.objects.filter(
        pk=doctor_id,
        provider_id=provider_id,
        provider__owner=request.user,
    ).first()
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    doctor.delete()


def get_doctor_detail(*, slug, request):
    doctor = (
        _doctor_detail_queryset()
        .filter(
            slug=slug,
            is_active=True,
            provider__is_active=True,
        )
        .first()
    )
    if doctor is None:
        raise DoctorNotFound("Doctor was not found.")

    return DoctorDetailSerializer(doctor, context={"request": request}).data


def _doctor_detail_queryset():
    return (
        Doctor.objects.select_related("provider", "provider__city")
        .prefetch_related(
            "specialties",
            "schedules",
            "provider__categories",
            "provider__provider_hours",
        )
    )


def find_doctor_specialty(specialty_key):
    return DoctorSpecialty.objects.filter(
        slug=specialty_key,
        is_active=True,
    ).first()


def _available_today_schedule_filter():
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()
    week_of_month = ((today.day - 1) // 7) + 1

    return (
        Q(schedules__is_active=True)
        & (
            Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.WEEKLY,
                schedules__weekday=today.weekday(),
            )
            | Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.MONTHLY_WEEKDAY,
                schedules__weekday=today.weekday(),
                schedules__week_of_month=week_of_month,
            )
            | Q(
                schedules__schedule_type=DoctorSchedule.ScheduleType.MONTHLY_DATE,
                schedules__day_of_month=today.day,
            )
        )
        & (
            Q(schedules__start_time__isnull=True, schedules__end_time__isnull=True)
            | Q(schedules__end_time__gt=current_time)
        )
    )


def _schedule_slot_sort_key(slot):
    schedule, date_value = slot
    slot_time = schedule.start_time or time.max
    return (
        date_value,
        slot_time,
        schedule.end_time or time.max,
    )
