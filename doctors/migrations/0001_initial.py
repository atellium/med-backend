# Generated manually to persist the existing DoctorSpecialty model.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DoctorSpecialty",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Singular name, e.g. Cardiologist",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Plural/display label, e.g. Cardiologists",
                        max_length=120,
                    ),
                ),
                ("slug", models.SlugField(max_length=120, unique=True)),
                (
                    "aliases",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Comma-separated search aliases, e.g. heart doctor, "
                            "heart specialist"
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "body_part",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("heart", "Heart"),
                            ("skin", "Skin"),
                            ("eye", "Eye"),
                            ("ent", "Ear, Nose & Throat"),
                            (
                                "brain_nervous_system",
                                "Brain & Nervous System",
                            ),
                            ("bones_joints", "Bones & Joints"),
                            ("lungs", "Lungs"),
                            ("kidney", "Kidney"),
                            (
                                "digestive_system",
                                "Stomach & Digestive System",
                            ),
                            ("liver", "Liver"),
                            ("teeth_mouth", "Teeth & Mouth"),
                            ("womens_health", "Women's Health"),
                            ("child_health", "Child Health"),
                            ("mental_health", "Mental Health"),
                            (
                                "hormones_metabolism",
                                "Hormones & Metabolism",
                            ),
                            ("urinary_system", "Urinary System"),
                            (
                                "reproductive_system",
                                "Reproductive System",
                            ),
                            ("blood", "Blood"),
                            ("cancer", "Cancer"),
                            ("general", "General Health"),
                            ("other", "Other"),
                        ],
                        help_text=(
                            "Primary body part or health system associated "
                            "with this specialty"
                        ),
                        max_length=50,
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="categories/",
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=[
                                    "jpg",
                                    "jpeg",
                                    "png",
                                    "webp",
                                    "avif",
                                ]
                            )
                        ],
                    ),
                ),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("is_featured", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Doctor Specialty",
                "verbose_name_plural": "Doctor Specialties",
                "db_table": "doctorspecialties",
                "ordering": ["sort_order", "name"],
            },
        ),
    ]
