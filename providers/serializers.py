from math import ceil

from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework import serializers

from providers.models import Provider, ProviderHour


CLOSING_SOON_MINUTES = 60


class ProviderListQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    radius_km = serializers.FloatField(
        required=False,
        min_value=0.1,
        max_value=100,
        default=5,
    )
    category = serializers.CharField(
        required=False,
        max_length=120,
        trim_whitespace=True,
        allow_blank=False,
    )
    is_verified = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    is_medicine_enquiry = serializers.BooleanField(required=False)
    is_test_book = serializers.BooleanField(required=False)
    open_now = serializers.BooleanField(required=False)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class MyProviderListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class ProviderBusinessUpdateSerializer(serializers.ModelSerializer):
    category_ids = serializers.PrimaryKeyRelatedField(
        source="categories",
        many=True,
        queryset=Provider.categories.field.remote_field.model.objects.filter(
            is_active=True
        ),
        required=False,
    )
    city_id = serializers.PrimaryKeyRelatedField(
        source="city",
        queryset=Provider._meta.get_field("city").remote_field.model.objects.all(),
        required=False,
        allow_null=True,
    )
    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
        required=False,
        allow_null=True,
        write_only=True,
    )
    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Provider
        fields = (
            "name",
            "category_ids",
            "description",
            "cover_image",
            "phone",
            "alternate_numbers",
            "whatsapp",
            "email",
            "website",
            "address",
            "landmark",
            "locality",
            "city_id",
            "pincode",
            "latitude",
            "longitude",
            "offerings",
            "services",
            "facilities",
            "is_medicine_enquiry",
            "is_test_book",
            "seo_title",
            "seo_description",
            "seo_keywords",
        )
        extra_kwargs = {
            "name": {"required": False},
            "address": {"required": False},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        latitude_provided = "latitude" in attrs
        longitude_provided = "longitude" in attrs

        if latitude_provided != longitude_provided:
            raise serializers.ValidationError(
                {
                    "location": (
                        "Latitude and longitude must either both be provided "
                        "or both be omitted."
                    )
                }
            )

        return attrs

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        latitude = validated_data.pop("latitude", serializers.empty)
        longitude = validated_data.pop("longitude", serializers.empty)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if latitude is not serializers.empty and longitude is not serializers.empty:
            instance.location = (
                Point(float(longitude), float(latitude), srid=4326)
                if latitude is not None and longitude is not None
                else None
            )

        instance.save()

        if categories is not None:
            instance.categories.set(categories)

        return instance


class ProviderListItemSerializer(serializers.ModelSerializer):
    distance_km = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    hour = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "cover_image",
            "distance_km",
            "is_verified",
            "is_featured",
            "is_active",
            "is_medicine_enquiry",
            "is_test_book",
            "offerings",
            "services",
            "facilities",
            "contact",
            "address",
            "city",
            "categories",
            "hour",
        )

    def get_distance_km(self, obj):
        distance = getattr(obj, "distance", None)
        if distance is None:
            return None
        return round(distance.km, 2)

    def get_cover_image(self, obj):
        if not obj.cover_image:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.cover_image.url)
        return obj.cover_image.url

    def get_contact(self, obj):
        return {
            "phone": _format_indian_phone(obj.phone),
            "alternate_numbers": obj.alternate_numbers,
            "whatsapp": _format_indian_phone(obj.whatsapp),
            "email": obj.email,
            "website": obj.website,
        }

    def get_address(self, obj):
        latitude = obj.location.y if obj.location else None
        longitude = obj.location.x if obj.location else None
        return {
            "address": obj.address,
            "landmark": obj.landmark,
            "locality": obj.locality,
            "pincode": obj.pincode,
            "latitude": latitude,
            "longitude": longitude,
        }

    def get_city(self, obj):
        if obj.city is None:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "slug": obj.city.slug,
            "state": obj.city.state.name,
        }

    def get_categories(self, obj):
        return [
            {
                "id": category.id,
                "name": category.name,
                "label": category.label,
                "slug": category.slug,
                "aliases": category.aliases,
            }
            for category in obj.categories.all()
        ]

    def get_hour(self, obj):
        return build_provider_hour_data(
            obj.provider_hours.all(),
            now=self.context.get("now"),
        )


class ProviderHourSerializer(serializers.ModelSerializer):
    day_names = serializers.ReadOnlyField()

    class Meta:
        model = ProviderHour
        fields = (
            "id",
            "days",
            "day_names",
            "opens_at",
            "closes_at",
        )


def build_provider_hour_data(hours, *, now=None):
    slots = sorted(hours, key=lambda hour: (min(hour.days), hour.opens_at, hour.id))
    now = now or timezone.localtime()
    current_day = now.weekday()
    current_time = now.time()
    current_slot = _current_slot(slots, current_day, current_time)

    if current_slot:
        minutes_until_close = _minutes_between(current_time, current_slot.closes_at)
        current_status = (
            "closing_soon"
            if minutes_until_close < CLOSING_SOON_MINUTES
            else "open"
        )
        next_closing_time = _format_time(current_slot.closes_at)
        opening_remark = f"until {_format_display_time(current_slot.closes_at)}"
    else:
        current_status = "closed"
        next_closing_time = None
        next_opening = _next_opening(slots, current_day, current_time)
        opening_remark = _opening_remark(next_opening)

    return {
        "current_opening_status": current_status,
        "next_closing_time": next_closing_time,
        "opening_remark": opening_remark,
        "schedule": _week_schedule(slots),
    }


def _current_slot(slots, current_day, current_time):
    for slot in slots:
        if (
            current_day in slot.days
            and slot.opens_at <= current_time < slot.closes_at
        ):
            return slot
    return None


def _next_opening(slots, current_day, current_time):
    for day_offset in range(7):
        day = (current_day + day_offset) % 7
        day_slots = sorted(
            (slot for slot in slots if day in slot.days),
            key=lambda slot: slot.opens_at,
        )
        for slot in day_slots:
            if day_offset > 0 or slot.opens_at > current_time:
                return {
                    "day": day,
                    "day_offset": day_offset,
                    "time": slot.opens_at,
                }
    return None


def _opening_remark(next_opening):
    if next_opening is None:
        return ""

    time_label = _format_display_time(next_opening["time"])
    day_offset = next_opening["day_offset"]
    if day_offset == 0:
        return f"opens today at {time_label}"
    if day_offset == 1:
        return f"opens tomorrow at {time_label}"

    day_name = dict(ProviderHour.Weekday.choices)[next_opening["day"]]
    return f"opens {day_name} at {time_label}"


def _week_schedule(slots):
    weekday_labels = dict(ProviderHour.Weekday.choices)
    return [
        {
            "day": day,
            "day_name": weekday_labels[day],
            "slots": [
                {
                    "id": str(slot.id) if slot.id else None,
                    "opens_at": _format_time(slot.opens_at),
                    "closes_at": _format_time(slot.closes_at),
                }
                for slot in slots
                if day in slot.days
            ],
        }
        for day in range(7)
    ]


def _minutes_between(start, end):
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def _format_time(value):
    return value.strftime("%H:%M:%S")


def _format_display_time(value):
    return value.strftime("%I:%M %p").lstrip("0").replace(":00", "")


class ProviderDetailSerializer(ProviderListItemSerializer):
    seo = serializers.SerializerMethodField()

    class Meta(ProviderListItemSerializer.Meta):
        fields = ProviderListItemSerializer.Meta.fields + ("seo",)

    def get_seo(self, obj):
        return {
            "title": obj.seo_title,
            "description": obj.seo_description,
            "keywords": obj.seo_keywords,
        }


def build_pagination(*, count, page, page_size):
    total_pages = ceil(count / page_size) if count else 0
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "next_page": page + 1 if page < total_pages else None,
        "previous_page": page - 1 if page > 1 and total_pages else None,
    }


def _format_indian_phone(value):
    if not value:
        return value
    value = str(value).strip()
    if value.startswith("+91"):
        return value
    return f"+91{value}"
