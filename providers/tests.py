from datetime import datetime, time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from locations.models import City, State
from providers.models import Provider, ProviderCategory, ProviderHour
from providers.serializers import (
    ProviderListQuerySerializer,
    _format_indian_phone,
    build_provider_hour_data,
)


class ProviderCategoryImageTests(TestCase):
    @staticmethod
    def image_upload(width, height, image_format="PNG"):
        content = BytesIO()
        Image.new("RGB", (width, height), "teal").save(content, format=image_format)
        return SimpleUploadedFile(
            f"category.{image_format.lower()}",
            content.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

    def test_category_image_is_compressed_without_webp_conversion(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                category = ProviderCategory.objects.create(
                    name="Pharmacy",
                    label="Pharmacies",
                    slug="pharmacy",
                    image=self.image_upload(600, 300, image_format="PNG"),
                )

                self.assertTrue(category.image.name.startswith("categories/"))
                self.assertTrue(category.image.name.endswith(".png"))

                with Image.open(category.image.path) as compressed:
                    self.assertEqual(compressed.format, "PNG")
                    self.assertEqual(compressed.size, (300, 150))

                self.assertTrue(Path(category.image.path).exists())


class ProviderListEndpointTests(APITestCase):
    def test_omitted_boolean_filters_are_not_treated_as_false(self):
        serializer = ProviderListQuerySerializer(
            data=QueryDict(
                "lat=22.467778888332326&lng=88.40233304308231&category=clinics"
            )
        )

        self.assertTrue(serializer.is_valid())
        self.assertNotIn("is_verified", serializer.validated_data)
        self.assertNotIn("is_featured", serializer.validated_data)
        self.assertNotIn("open_now", serializer.validated_data)

    def setUp(self):
        self.state = State.objects.create(
            name="West Bengal",
            slug="west-bengal",
            code="WB",
        )
        self.city = City.objects.create(
            name="Kolkata",
            slug="kolkata",
            state=self.state,
        )

    def test_formats_indian_phone_numbers_for_response(self):
        self.assertEqual(_format_indian_phone("9800000001"), "+919800000001")
        self.assertEqual(_format_indian_phone("+919800000001"), "+919800000001")
        self.assertEqual(_format_indian_phone(""), "")

    def test_lists_nearby_providers_with_grouped_fields(self):
        category = ProviderCategory.objects.create(
            name="Pharmacy",
            label="Pharmacies",
            slug="pharmacies",
        )
        provider = Provider.objects.create(
            name="CarePlus Pharmacy",
            locality="Garia",
            city=self.city,
            address="1 Demo Road",
            phone="9800000001",
            location=Point(88.40233304308231, 22.467778888332326, srid=4326),
            offerings=["medicine"],
            services=["delivery"],
            facilities=["parking"],
            is_verified=True,
        )
        provider.categories.set([category])
        ProviderHour.objects.create(
            provider=provider,
            days=[0, 1, 2, 3, 4],
            opens_at=time(9, 0),
            closes_at=time(17, 30),
        )

        response = self.client.get(
            reverse("providers:provider-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "category": category.slug,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertIsNone(data["pagination"]["next_page"])
        self.assertEqual(data["category"]["slug"], "pharmacies")
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "CarePlus Pharmacy")
        self.assertEqual(data["results"][0]["distance_km"], 0)
        self.assertEqual(data["results"][0]["offerings"], ["medicine"])
        self.assertEqual(data["results"][0]["contact"]["phone"], "+919800000001")
        self.assertEqual(data["results"][0]["address"]["locality"], "Garia")
        self.assertEqual(data["results"][0]["city"]["state"], "West Bengal")
        self.assertEqual(data["results"][0]["categories"][0]["slug"], "pharmacies")
        hour = data["results"][0]["hour"]
        self.assertIn(
            hour["current_opening_status"],
            ["open", "closing_soon", "closed"],
        )
        self.assertEqual(hour["schedule"][0]["day_name"], "Monday")
        self.assertIsNotNone(hour["schedule"][0]["slots"][0]["id"])
        self.assertEqual(
            {
                "opens_at": hour["schedule"][0]["slots"][0]["opens_at"],
                "closes_at": hour["schedule"][0]["slots"][0]["closes_at"],
            },
            {"opens_at": "09:00:00", "closes_at": "17:30:00"},
        )
        self.assertEqual(hour["schedule"][5]["slots"], [])

    def test_verified_filter_is_subset_of_category_results(self):
        clinics = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        diagnostics = ProviderCategory.objects.create(
            name="Diagnostic Center",
            label="Diagnostic Centers",
            slug="diagnostics",
        )
        self._provider("Verified Clinic", clinics, is_verified=True)
        self._provider("Unverified Clinic", clinics, is_verified=False)
        self._provider("Verified Diagnostic", diagnostics, is_verified=True)

        base_query = {
            "lat": "22.467778888332326",
            "lng": "88.40233304308231",
            "category": "clinics",
        }
        all_clinics = self.client.get(reverse("providers:provider-list"), base_query)
        verified_clinics = self.client.get(
            reverse("providers:provider-list"),
            {**base_query, "is_verified": "true"},
        )

        self.assertEqual(all_clinics.status_code, status.HTTP_200_OK)
        self.assertEqual(verified_clinics.status_code, status.HTTP_200_OK)
        self.assertEqual(all_clinics.json()["pagination"]["count"], 2)
        self.assertEqual(verified_clinics.json()["pagination"]["count"], 1)
        self.assertEqual(
            verified_clinics.json()["results"][0]["name"],
            "Verified Clinic",
        )

    def test_open_now_filter_returns_only_currently_open_providers(self):
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        open_provider = self._provider("Open Clinic", category, is_verified=True)
        closed_provider = self._provider("Closed Clinic", category, is_verified=True)
        no_hours_provider = self._provider(
            "No Hours Clinic",
            category,
            is_verified=True,
        )
        tomorrow_provider = self._provider(
            "Tomorrow Clinic",
            category,
            is_verified=True,
        )
        ProviderHour.objects.create(
            provider=open_provider,
            days=[2],
            opens_at=time(9, 0),
            closes_at=time(17, 0),
        )
        ProviderHour.objects.create(
            provider=closed_provider,
            days=[2],
            opens_at=time(15, 0),
            closes_at=time(18, 0),
        )
        ProviderHour.objects.create(
            provider=tomorrow_provider,
            days=[3],
            opens_at=time(9, 0),
            closes_at=time(17, 0),
        )

        with patch(
            "providers.services.timezone.localtime",
            return_value=_kolkata_datetime(2026, 9, 9, 10, 0),
        ):
            response = self.client.get(
                reverse("providers:provider-list"),
                {
                    "lat": "22.467778888332326",
                    "lng": "88.40233304308231",
                    "open_now": "true",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 2)
        self.assertEqual(
            {provider["name"] for provider in data["results"]},
            {"Open Clinic", "No Hours Clinic"},
        )
        no_hours_result = next(
            provider
            for provider in data["results"]
            if provider["name"] == "No Hours Clinic"
        )
        self.assertEqual(no_hours_result["id"], str(no_hours_provider.id))
        self.assertEqual(no_hours_result["hour"]["schedule"][0]["slots"], [])

    def test_open_now_false_returns_currently_closed_providers(self):
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        open_provider = self._provider("Open Clinic", category, is_verified=True)
        closed_provider = self._provider("Closed Clinic", category, is_verified=True)
        no_hours_provider = self._provider(
            "No Hours Clinic",
            category,
            is_verified=True,
        )
        ProviderHour.objects.create(
            provider=open_provider,
            days=[2],
            opens_at=time(9, 0),
            closes_at=time(17, 0),
        )
        ProviderHour.objects.create(
            provider=closed_provider,
            days=[2],
            opens_at=time(15, 0),
            closes_at=time(18, 0),
        )

        with patch(
            "providers.services.timezone.localtime",
            return_value=_kolkata_datetime(2026, 9, 9, 10, 0),
        ):
            response = self.client.get(
                reverse("providers:provider-list"),
                {
                    "lat": "22.467778888332326",
                    "lng": "88.40233304308231",
                    "open_now": "false",
                },
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Closed Clinic")

    def test_rejects_unknown_query_parameter(self):
        response = self.client.get(
            reverse("providers:provider-list"),
            {
                "lat": "22.467778888332326",
                "lng": "88.40233304308231",
                "is\\_verified": "true",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_provider_detail_by_slug(self):
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        provider = self._provider("Detail Clinic", category, is_verified=True)
        provider.seo_title = "Detail Clinic SEO"
        provider.seo_description = "Detail Clinic description"
        provider.seo_keywords = "clinic, care"
        provider.save()
        ProviderHour.objects.create(
            provider=provider,
            days=[5],
            opens_at=time(10, 0),
            closes_at=time(14, 0),
        )

        response = self.client.get(
            reverse("providers:provider-detail", kwargs={"slug": provider.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["slug"], provider.slug)
        self.assertEqual(data["name"], "Detail Clinic")
        self.assertEqual(data["contact"]["phone"], "+919800000001")
        self.assertEqual(data["address"]["locality"], "Garia")
        self.assertEqual(data["city"]["state"], "West Bengal")
        self.assertEqual(data["categories"][0]["slug"], "clinics")
        self.assertEqual(data["hour"]["schedule"][5]["day_name"], "Saturday")
        self.assertIsNotNone(data["hour"]["schedule"][5]["slots"][0]["id"])
        self.assertEqual(
            {
                "opens_at": data["hour"]["schedule"][5]["slots"][0]["opens_at"],
                "closes_at": data["hour"]["schedule"][5]["slots"][0]["closes_at"],
            },
            {"opens_at": "10:00:00", "closes_at": "14:00:00"},
        )
        self.assertEqual(data["seo"]["title"], "Detail Clinic SEO")

    def test_provider_detail_ignores_inactive_provider(self):
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        provider = self._provider("Inactive Clinic", category, is_verified=True)
        provider.is_active = False
        provider.save()

        response = self.client.get(
            reverse("providers:provider-detail", kwargs={"slug": provider.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_my_provider_list_requires_authentication(self):
        response = self.client.get(reverse("providers:my-provider-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_only_providers_owned_by_logged_in_user(self):
        user = User.objects.create_user(phone="+919876543210")
        other_user = User.objects.create_user(phone="+919876543211")
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        owned_provider = self._provider(
            "Owned Clinic",
            category,
            is_verified=True,
            owner=user,
        )
        self._provider(
            "Other Clinic",
            category,
            is_verified=True,
            owner=other_user,
        )
        self._provider("Unowned Clinic", category, is_verified=True)

        self.client.force_authenticate(user)
        response = self.client.get(reverse("providers:my-provider-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["pagination"]["count"], 1)
        self.assertEqual(data["results"][0]["id"], str(owned_provider.id))
        self.assertEqual(data["results"][0]["name"], "Owned Clinic")
        self.assertIsNone(data["results"][0]["distance_km"])

    def test_my_provider_list_rejects_unknown_query_parameter(self):
        user = User.objects.create_user(phone="+919876543210")
        self.client.force_authenticate(user)

        response = self.client.get(
            reverse("providers:my-provider-list"),
            {"lat": "22.467778888332326"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_updates_owned_provider_business(self):
        user = User.objects.create_user(phone="+919876543210")
        clinic = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        diagnostic = ProviderCategory.objects.create(
            name="Diagnostic Center",
            label="Diagnostic Centers",
            slug="diagnostics",
        )
        provider = self._provider(
            "Old Clinic",
            clinic,
            is_verified=True,
            owner=user,
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse(
                "providers:my-provider-business-detail",
                kwargs={"provider_id": provider.id},
            ),
            {
                "name": "Updated Clinic",
                "category_ids": [diagnostic.id],
                "description": "Updated business profile.",
                "phone": "+919800000002",
                "address": "2 Updated Road",
                "locality": "Jadavpur",
                "city_id": self.city.id,
                "latitude": 22.498,
                "longitude": 88.371,
                "offerings": ["consultation"],
                "services": ["appointments"],
                "facilities": ["wheelchair"],
                "seo_title": "Updated Clinic SEO",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["name"], "Updated Clinic")
        self.assertEqual(data["categories"][0]["slug"], "diagnostics")
        self.assertEqual(data["contact"]["phone"], "+919800000002")
        self.assertEqual(data["address"]["address"], "2 Updated Road")
        self.assertEqual(data["city"]["state"], "West Bengal")
        self.assertEqual(data["address"]["latitude"], 22.498)
        self.assertEqual(data["address"]["longitude"], 88.371)
        self.assertEqual(data["offerings"], ["consultation"])
        self.assertEqual(data["seo"]["title"], "Updated Clinic SEO")

        provider.refresh_from_db()
        self.assertEqual(provider.name, "Updated Clinic")
        self.assertEqual(provider.categories.get(), diagnostic)
        self.assertEqual(provider.location.y, 22.498)
        self.assertEqual(provider.location.x, 88.371)

    def test_cannot_update_provider_owned_by_another_user(self):
        user = User.objects.create_user(phone="+919876543210")
        other_user = User.objects.create_user(phone="+919876543211")
        category = ProviderCategory.objects.create(
            name="Clinic",
            label="Clinics",
            slug="clinics",
        )
        provider = self._provider(
            "Other Clinic",
            category,
            is_verified=True,
            owner=other_user,
        )

        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse(
                "providers:my-provider-business-detail",
                kwargs={"provider_id": provider.id},
            ),
            {"name": "Should Not Save"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        provider.refresh_from_db()
        self.assertEqual(provider.name, "Other Clinic")

    def _provider(self, name, category, *, is_verified, owner=None):
        provider = Provider.objects.create(
            name=name,
            locality="Garia",
            city=self.city,
            address="1 Demo Road",
            phone="9800000001",
            location=Point(88.40233304308231, 22.467778888332326, srid=4326),
            is_verified=is_verified,
            owner=owner,
        )
        provider.categories.set([category])
        return provider


class ProviderHourSerializerTests(TestCase):
    def test_returns_open_status_with_closing_time_and_full_schedule(self):
        hour = ProviderHour(
            days=[0, 1, 2, 3, 4],
            opens_at=time(9, 0),
            closes_at=time(17, 30),
        )

        data = build_provider_hour_data(
            [hour],
            now=_kolkata_datetime(2026, 9, 9, 10, 0),
        )

        self.assertEqual(data["current_opening_status"], "open")
        self.assertEqual(data["next_closing_time"], "17:30:00")
        self.assertEqual(data["opening_remark"], "until 5:30 PM")
        self.assertEqual(len(data["schedule"]), 7)
        self.assertEqual(data["schedule"][2]["day_name"], "Wednesday")
        self.assertIsNone(data["schedule"][2]["slots"][0]["id"])
        self.assertEqual(
            {
                "opens_at": data["schedule"][2]["slots"][0]["opens_at"],
                "closes_at": data["schedule"][2]["slots"][0]["closes_at"],
            },
            {"opens_at": "09:00:00", "closes_at": "17:30:00"},
        )

    def test_returns_closing_soon_status(self):
        hour = ProviderHour(
            days=[2],
            opens_at=time(9, 0),
            closes_at=time(17, 30),
        )

        data = build_provider_hour_data(
            [hour],
            now=_kolkata_datetime(2026, 9, 9, 17, 10),
        )

        self.assertEqual(data["current_opening_status"], "closing_soon")
        self.assertEqual(data["next_closing_time"], "17:30:00")
        self.assertEqual(data["opening_remark"], "until 5:30 PM")

    def test_returns_open_status_when_closing_time_is_one_hour_away(self):
        hour = ProviderHour(
            days=[2],
            opens_at=time(9, 0),
            closes_at=time(17, 30),
        )

        data = build_provider_hour_data(
            [hour],
            now=_kolkata_datetime(2026, 9, 9, 16, 30),
        )

        self.assertEqual(data["current_opening_status"], "open")

    def test_returns_closed_status_with_next_opening_remark(self):
        hour = ProviderHour(
            days=[2, 3],
            opens_at=time(9, 0),
            closes_at=time(17, 30),
        )

        opens_today = build_provider_hour_data(
            [hour],
            now=_kolkata_datetime(2026, 9, 9, 8, 0),
        )
        opens_tomorrow = build_provider_hour_data(
            [hour],
            now=_kolkata_datetime(2026, 9, 9, 18, 0),
        )

        self.assertEqual(opens_today["current_opening_status"], "closed")
        self.assertIsNone(opens_today["next_closing_time"])
        self.assertEqual(opens_today["opening_remark"], "opens today at 9 AM")
        self.assertEqual(opens_tomorrow["opening_remark"], "opens tomorrow at 9 AM")


def _kolkata_datetime(year, month, day, hour, minute):
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
