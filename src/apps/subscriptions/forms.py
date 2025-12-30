from allauth.account.forms import SignupForm
from django import forms
from django.core.exceptions import ValidationError

from apps.subscriptions.models import Customer

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    has_user_agreed_tos_and_privacy = forms.BooleanField(
        required=True,
        error_messages={
            "required": "You must agree to the Terms of Service and Privacy Policy."
        },
    )

    def clean_has_user_agreed_tos_and_privacy(self):
        value = self.cleaned_data.get("has_user_agreed_tos_and_privacy")
        if not value:
            raise ValidationError(
                "You must agree to the Terms of Service and Privacy Policy."
            )
        return value

    def save(self, request):
        user = super().save(request)

        # Save Names
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.save(update_fields=["first_name", "last_name"])

        agreed = self.cleaned_data["has_user_agreed_tos_and_privacy"]

        # Consent Agreement
        Customer.objects.update_or_create(
            user=user,
            defaults={
                "has_user_agreed_tos_and_privacy": agreed
            },
        )

        return user
