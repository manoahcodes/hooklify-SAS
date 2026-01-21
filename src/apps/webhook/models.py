from django.db import models

# Create your models here.
class WebhookEvents(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_id"])
        ]

    def __str__(self):
        return f"{self.event_type}"