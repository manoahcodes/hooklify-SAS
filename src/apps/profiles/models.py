from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class ContactChoices(models.TextChoices):
        QUESTIONS = "question", "Question"
        REQUESTS = "requests", "Request"
        ISSUES = "issues", "Issue"

class ContactMessage(models.Model):
    name = models.CharField(max_length=255, null=False, blank=False)
    email = models.EmailField(null=False, blank=False)
    topic = models.CharField(max_length=50, choices=ContactChoices.choices, default=ContactChoices.QUESTIONS)
    message = models.TextField(null=False, blank=False)
    status = models.BooleanField(default=False)  # Whether the message has been addressed
    has_user_agreed_tos = models.BooleanField(default=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.topic}"
    

class ProfileSettings(models.Model):
     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="account_settings")
     email_notifications = models.BooleanField(default=True)
     push_notifications = models.BooleanField(default=True)
     generation_notifications = models.BooleanField(default=True)
     viral_alert_notifications = models.BooleanField(default=True)
     low_credits_notifications = models.BooleanField(default=True)

     def __str__(self):
          return f"{self.user}"