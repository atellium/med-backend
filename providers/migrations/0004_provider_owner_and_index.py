# Generated manually because local GeoDjango setup cannot load GDAL.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("providers", "0003_providerhour"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="providers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="provider",
            index=models.Index(
                fields=["owner", "is_active"],
                name="providers_owner__4ee99d_idx",
            ),
        ),
    ]
