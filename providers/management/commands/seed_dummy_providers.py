import math
import random

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from locations.models import City
from providers.models import Provider, ProviderCategory


CENTER_LATITUDE = 22.467778888332326
CENTER_LONGITUDE = 88.40233304308231
DEFAULT_RADIUS_KM = 10
DEFAULT_CITY_ID = 1
DEFAULT_CATEGORY_ID = 2

PROVIDER_NAMES = [
    "MediCare Health Point",
    "LifeLine Clinic",
    "Apollo Care Hub",
    "Wellness Medical Center",
    "HealthFirst Diagnostic",
    "CarePlus Pharmacy",
    "City Health Clinic",
    "Prime Medical Store",
    "Green Cross Healthcare",
    "Metro Wellness Center",
    "Family Care Clinic",
    "Sunrise Medical Hub",
    "TrustCare Diagnostics",
    "Relief Pharmacy",
    "Modern Health Centre",
    "QuickCare Clinic",
    "Hope Medical Store",
    "Urban Health Point",
    "BetterLife Clinic",
    "CareBridge Healthcare",
    "SafeHealth Pharmacy",
    "NorthStar Clinic",
    "PeopleCare Medical",
    "HealWell Center",
    "MedNearby Demo Provider",
]

LOCALITIES = [
    "Garia",
    "Narendrapur",
    "Sonarpur",
    "Patuli",
    "Mukundapur",
    "Bansdroni",
    "Jadavpur",
    "Santoshpur",
    "Baruipur",
    "Ruby",
]


class Command(BaseCommand):
    help = "Create repeatable dummy providers around a fixed latitude/longitude."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=len(PROVIDER_NAMES),
            help="Number of dummy providers to create or update.",
        )
        parser.add_argument(
            "--radius-km",
            type=float,
            default=DEFAULT_RADIUS_KM,
            help="Maximum distance in kilometers from the center point.",
        )
        parser.add_argument(
            "--city-id",
            type=int,
            default=DEFAULT_CITY_ID,
            help="City ID assigned to every dummy provider.",
        )
        parser.add_argument(
            "--category-id",
            type=int,
            default=DEFAULT_CATEGORY_ID,
            help="Provider category ID assigned to every dummy provider.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260909,
            help="Random seed for repeatable coordinates.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        radius_km = options["radius_km"]
        if count < 1:
            raise CommandError("count must be at least 1.")
        if radius_km <= 0:
            raise CommandError("radius-km must be greater than 0.")

        city = City.objects.filter(pk=options["city_id"]).first()
        if city is None:
            raise CommandError(f"City with ID {options['city_id']} does not exist.")

        category = ProviderCategory.objects.filter(pk=options["category_id"]).first()
        if category is None:
            raise CommandError(
                f"Provider category with ID {options['category_id']} does not exist."
            )

        rng = random.Random(options["seed"])
        created_count = 0
        updated_count = 0

        for index in range(count):
            name = _provider_name(index)
            locality = LOCALITIES[index % len(LOCALITIES)]
            latitude, longitude = _random_point_within_radius(
                rng,
                CENTER_LATITUDE,
                CENTER_LONGITUDE,
                radius_km,
            )
            provider, created = Provider.objects.update_or_create(
                name=name,
                locality=locality,
                defaults={
                    "description": (
                        f"Dummy healthcare provider in {locality} for local testing."
                    ),
                    "phone": f"98{index + 1:08d}",
                    "alternate_numbers": [f"97{index + 1:08d}"],
                    "whatsapp": f"98{index + 1:08d}",
                    "email": f"provider{index + 1}@example.com",
                    "website": f"https://provider{index + 1}.example.com",
                    "address": f"{index + 1}, Demo Healthcare Road",
                    "landmark": "Near main road",
                    "city": city,
                    "pincode": f"700{index % 100:03d}",
                    "location": Point(longitude, latitude, srid=4326),
                    "offerings": ["walk-in consultation", "home sample collection"],
                    "services": ["consultation", "basic checkup"],
                    "facilities": ["parking", "online booking"],
                    "is_verified": index % 3 != 0,
                    "is_featured": index < 5,
                    "is_active": True,
                },
            )
            provider.categories.set([category])
            created_count += int(created)
            updated_count += int(not created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} dummy providers within {radius_km:g} km: "
                f"{created_count} created, {updated_count} updated."
            )
        )


def _provider_name(index):
    if index < len(PROVIDER_NAMES):
        return PROVIDER_NAMES[index]
    return f"MedNearby Demo Provider {index + 1}"


def _random_point_within_radius(rng, center_latitude, center_longitude, radius_km):
    earth_radius_km = 6371.0088
    distance_km = radius_km * math.sqrt(rng.random())
    bearing = 2 * math.pi * rng.random()

    angular_distance = distance_km / earth_radius_km
    center_latitude_rad = math.radians(center_latitude)
    center_longitude_rad = math.radians(center_longitude)

    latitude_rad = math.asin(
        math.sin(center_latitude_rad) * math.cos(angular_distance)
        + math.cos(center_latitude_rad)
        * math.sin(angular_distance)
        * math.cos(bearing)
    )
    longitude_rad = center_longitude_rad + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(center_latitude_rad),
        math.cos(angular_distance)
        - math.sin(center_latitude_rad) * math.sin(latitude_rad),
    )

    longitude = (math.degrees(longitude_rad) + 540) % 360 - 180
    latitude = math.degrees(latitude_rad)
    return latitude, longitude
