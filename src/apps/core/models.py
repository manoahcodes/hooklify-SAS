from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

# Create your models here.
class Platform(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=100, blank=True, null=True)
    system_prompt = models.TextField(null=True, blank=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Platform.", null=True, blank=True)

    def __str__(self):
        return self.name

class Niche(models.Model):
    """
    Examples: 
    - Name: "Entertainment"
    - Description: "This niche handles comedies, skits, and viral entertainment."
    """
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Niche.", null=True)
    description = models.TextField(help_text="Context for the AI to understand this niche.")

    def __str__(self):
        return self.name
    
class VideoDuration(models.Model):
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Sub-Niche.", null=True)

    def __str__(self):
        return self.name
    
class SubNiche(models.Model):
    """
    Examples: 
    - Name: "Comedy"
    - Description: "This comedy niche handles comedies, and skits."
    """
    niche = models.ForeignKey(Niche, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this sub niche.")
    metadata = models.JSONField(help_text="Context for the AI to understand this sub niche.", blank=True, null=True)

    def __str__(self):
        return self.name

class Tone(models.Model):
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Tone.", null=True)
    description = models.TextField(help_text="Context for the AI to understand this Tone.")
    
    def __str__(self):
        return self.name
    
class Style(models.Model):
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this style.", null=True)
    description = models.TextField(help_text="Context for the AI to understand this Style.")

    def __str__(self):
        return self.name
    
class Region(models.Model):
    """Standardized Country/Region list"""
    name = models.CharField(max_length=100)
    iso2 = models.CharField(max_length=2, unique=True, help_text="ISO 3166-1 alpha-2 (e.g., US)")
    iso3 = models.CharField(max_length=3, unique=True, help_text="ISO 3166-1 alpha-3 (e.g., USA)")
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Country.", null=True)
    
    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.iso2})"
    
class AgeGroup(models.Model):
    """Ranges like '18-24', '25-34'"""
    label = models.CharField(max_length=50, unique=True)
    range = models.CharField(max_length=6, unique=True, null=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Age Group.", null=True)
    description = models.TextField(help_text="Context for the AI to understand this Age Group.", null=True)
    
    def __str__(self):
        return f"{self.label} - {self.range}"
    
    class Meta:
        ordering = ['id']

class Audience(models.Model):
    """Specific segments like 'Entrepreneurs', 'Gen Z', etc."""
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Audience.", null=True)
    description = models.TextField(help_text="Context for the AI to understand this Audience.")
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class Outcome(models.Model):
    name = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(help_text="JSON Context for the AI to understand this Audience.", null=True, blank=True)

    def __str__(self):
        return self.name

class Generation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="generations")
    title = models.CharField(max_length=255)
    platform = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, blank=False)

    # Context
    niche = models.ForeignKey(Niche, on_delete=models.SET_NULL, null=True)
    sub_niche = models.ForeignKey(SubNiche, on_delete=models.SET_NULL, null=True)
    video_duration = models.ForeignKey(VideoDuration, on_delete=models.SET_NULL, null=True)
    country = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True)

    target_audiences = models.ManyToManyField(Audience, blank=True)
    age_groups = models.ManyToManyField(AgeGroup, blank=True)
    desired_tones = models.ManyToManyField(Tone, blank=True)
    visual_styles = models.ManyToManyField(Style, blank=True)
    endgoal = models.ManyToManyField(Outcome, blank=True)

    # --- Media & References ---
    # The primary video reference (Visual/Vibe match)
    video_reference_url = models.URLField(
        blank=True, 
        null=True,
        help_text="A specific Shorts/Reels/TikTok link that captures the visual vibe you want."
    )

    # Specific instructions
    core_concept = models.TextField()
    
    generate_hooks = models.BooleanField(default=True)
    generate_scripts = models.BooleanField(default=True)
    generate_cta = models.BooleanField(default=False)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    

class ReferenceLink(models.Model):
    """
    Allows up to 3 informational links (articles, competitors, blogs).
    """
    project = models.ForeignKey(Generation, on_delete=models.CASCADE, related_name="reference_links")
    url = models.URLField()
    
    def __str__(self):
        return self.url
    

class Notification(models.Model):
    # Categories map to your specific SaaS needs
    class NotificationChoices(models.TextChoices):
        SUCCESS = "success", ("Success")   # Task complete, Export ready
        ERROR = "error", ("Error")         # Payment failed, Export failed
        WARNING = "warning", ("Warning")   # Trial ending, Usage limit approached
        INFO = "info", ("System")          # Feature announcement, Maintenance

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', blank=True, null=True)
    category = models.CharField(max_length=20, choices=NotificationChoices.choices, default=NotificationChoices.INFO)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)

    # --- The Linking Logic ---
    # Option A: Link to an internal object (e.g., a specific Project or Invoice)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Option B: Link to an external URL (e.g., Blog post, Help doc)
    external_link = models.URLField(max_length=500, null=True, blank=True, help_text="Used if not linked to an internal object")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_not_system_msg(self):
        return self.category in {
            self.NotificationChoices.SUCCESS,
            self.NotificationChoices.ERROR,
            self.NotificationChoices.WARNING,
        }
    
    @property
    def get_redirect_url(self):
        """
        Smart logic to decide where the user goes when they click.
        Priority: External Link > Internal Object's get_absolute_url > Home
        """
        if self.external_link:
            return self.external_link
        
        if self.content_object and hasattr(self.content_object, 'get_absolute_url'):
            return self.content_object.get_absolute_url()
            
        return reverse('dashboard')