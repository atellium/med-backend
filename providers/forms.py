from django import forms
from django.contrib.gis.geos import Point

from providers.models import Provider


class ProviderAdminForm(forms.ModelForm):
    latitude = forms.DecimalField(
        required=False,
        min_value=-90,
        max_value=90,
    )
    longitude = forms.DecimalField(
        required=False,
        min_value=-180,
        max_value=180,
    )

    class Meta:
        model = Provider
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.location:
            self.fields["latitude"].initial = self.instance.location.y
            self.fields["longitude"].initial = self.instance.location.x

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")

        if (latitude is None) != (longitude is None):
            raise forms.ValidationError(
                "Latitude and longitude must either both be provided or both be empty."
            )
        return cleaned_data

    def save(self, commit=True):
        provider = super().save(commit=False)
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")
        provider.location = (
            Point(float(longitude), float(latitude), srid=4326)
            if latitude is not None and longitude is not None
            else None
        )

        if commit:
            provider.save()
            self.save_m2m()
        return provider
