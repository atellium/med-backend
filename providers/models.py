import uuid
from django.conf import settings
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from core.models import AutoSlugModel, TimestampedModel, SEOModel
from core.image_service import compress_image
from core.utils import generate_unique_slug

from providers.validators import (
    validate_alternate_numbers,
    validate_provider_days,
    validate_established_year,
    validate_social_urls,
)

class ProviderCategory(AutoSlugModel, TimestampedModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Singular name, e.g. Pharmacy"
    )
    label = models.CharField(
        max_length=120,
        help_text="Plural/display label, e.g. Pharmacies"
    )
    slug = models.SlugField(
        max_length=120,
        unique=True
    )

    aliases = models.CharField(
        max_length=300,
        blank=True,
        help_text="Comma-separated search aliases"
    )

    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg","jpeg","png","webp","avif",])
        ],
    )

    sort_order = models.PositiveSmallIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        db_table = "provider_categories"
        ordering = ["sort_order", "name"]
        verbose_name = "Healthcare Provider Category"
        verbose_name_plural = "Healthcare Provider Categories"
        indexes = [
            models.Index(fields=["is_active", "sort_order", "name"]),
            models.Index(fields=["is_featured", "sort_order"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.image and not self.image._committed:
            self.image = compress_image(
                self.image,
                quality=100,
                max_width=300,
                convert_to_webp=False,
            )
        super().save(*args, **kwargs)


class Provider(TimestampedModel, SEOModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=200,
        db_index=True,
    )

    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        db_index=True,
    )

    categories = models.ManyToManyField(
        "ProviderCategory",
        related_name="providers",
        blank=True,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="providers",
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
    )

    cover_image = models.ImageField(
        upload_to="providers/covers/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp", "avif",]
            )
        ],
    )

    # Contact
    phone = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
    )

    alternate_numbers = models.JSONField(
        blank=True,
        default=list,
    )

    whatsapp = models.CharField(
        max_length=20,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    website = models.URLField(
        blank=True,
    )

    # Address
    address = models.CharField(
        max_length=255,
    )

    landmark = models.CharField(
        max_length=150,
        blank=True,
    )

    locality = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
    )

    city = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        related_name="providers",
        blank=True,
        null=True,
    )

    pincode = models.CharField(
        max_length=10,
        blank=True,
        db_index=True,
    )

    location = gis_models.PointField(
        geography=True,
        srid=4326,
        blank=True,
        null=True,
        spatial_index=True,
        help_text="Provider location as longitude/latitude point",
    )

    # Display/catalog info
    offerings = models.JSONField(
        default=list,
        blank=True,
    )
    services = models.JSONField(
        default=list,
        blank=True,
    )
    facilities = models.JSONField(
        default=list,
        blank=True,
    )

    # Status
    is_verified = models.BooleanField(
        default=False,
    )
    is_featured = models.BooleanField(
        default=False,
    )
    is_active = models.BooleanField(
        default=True,
    )

    is_medicine_enquiry = models.BooleanField(
        default=False,
    )
    is_test_book = models.BooleanField(
        default=False,
    )

    class Meta:
        db_table = "providers"
        ordering = ["-is_featured", "name"]

        indexes = [
            models.Index(fields=["is_active", "city"]),
            models.Index(fields=["is_active", "locality"]),
            models.Index(fields=["is_verified", "is_active"]),
            models.Index(fields=["is_featured", "is_active"]),
            models.Index(fields=["owner", "is_active"]),
        ]

        verbose_name = "Provider"
        verbose_name_plural = "Providers"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        slug_source = f"{self.name} {self.locality}".strip()
        self.slug = generate_unique_slug(
            self,
            slug_source,
            fallback="provider",
            using=kwargs.get("using"),
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"slug"}

        if self.cover_image and not self.cover_image._committed:
            self.cover_image = compress_image(
                self.cover_image,
                quality=80,
                max_width=1024,
                convert_to_webp=True,
            )

        super().save(*args, **kwargs)


class ProviderHour(TimestampedModel):
    """One opening-time slot shared by one or more weekdays."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="provider_hours",
    )

    days = ArrayField(
        models.PositiveSmallIntegerField(
            choices=Weekday.choices,
        ),
        size=7,
        validators=[validate_provider_days],
        help_text="Weekdays sharing this slot (Monday=0, Sunday=6).",
    )

    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        db_table = "provider_hours"

        ordering = (
            "provider_id",
            "opens_at",
            "id",
        )

        indexes = [
            models.Index(
                fields=("provider", "opens_at"),
                name="provider_hours_open_idx",
            ),
            GinIndex(
                fields=("days",),
                name="provider_hours_days_gin",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    closes_at__gt=models.F("opens_at")
                ),
                name="provider_hour_closes_after_open",
            ),
            models.UniqueConstraint(
                fields=(
                    "provider",
                    "days",
                    "opens_at",
                    "closes_at",
                ),
                name="provider_hour_slot_unique",
            ),
        ]

    def clean(self):
        super().clean()

        validate_provider_days(self.days)
        self.days = sorted(set(self.days))

        if (
            self.opens_at is not None
            and self.closes_at is not None
            and self.closes_at <= self.opens_at
        ):
            raise ValidationError(
                {
                    "closes_at":
                        "Closing time must be later than opening time."
                }
            )

        if (
            self.provider_id
            and self.opens_at is not None
            and self.closes_at is not None
            and self.closes_at > self.opens_at
        ):
            overlaps = (
                type(self)
                .objects
                .filter(
                    provider_id=self.provider_id,
                    days__overlap=self.days,
                    opens_at__lt=self.closes_at,
                    closes_at__gt=self.opens_at,
                )
                .exclude(pk=self.pk)
            )

            if overlaps.exists():
                raise ValidationError(
                    "This slot overlaps existing provider hours "
                    "on one or more selected days."
                )

    def save(self, *args, **kwargs):
        validate_provider_days(self.days)
        self.days = sorted(set(self.days))

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"days"}

        return super().save(*args, **kwargs)

    @property
    def day_names(self):
        labels = dict(self.Weekday.choices)

        return [
            labels[day]
            for day in self.days
        ]

    def __str__(self):
        days = ", ".join(self.day_names)

        return (
            f"{self.provider}: {days} "
            f"{self.opens_at:%H:%M}-"
            f"{self.closes_at:%H:%M}"
        )
