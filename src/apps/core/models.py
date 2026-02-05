from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator


# Create your models here.
class Niche(models.Model):
    """
    Examples: 
    - Name: "Entertainment"
    - Description: "This niche handles comedies, skits, and viral entertainment."
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this niche.")

    def __str__(self):
        return self.name
    
class SubNiche(models.Model):
    """
    Examples: 
    - Name: "Entertainment"
    - Description: "This niche handles comedies, skits, and viral entertainment."
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this sub niche.")

    def __str__(self):
        return self.name

class Tone(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this Tone.")
    
    def __str__(self):
        return self.name
    
class Style(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this Style.")

    def __str__(self):
        return self.name
    
class Country(models.Model):
    """Standardized Country/Region list"""
    name = models.CharField(max_length=100)
    iso2 = models.CharField(max_length=2, unique=True, help_text="ISO 3166-1 alpha-2 (e.g., US)")
    iso3 = models.CharField(max_length=3, unique=True, help_text="ISO 3166-1 alpha-3 (e.g., USA)")
    
    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.iso2})"
    
class AgeGroup(models.Model):
    """Ranges like '18-24', '25-34'"""
    label = models.CharField(max_length=50, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this Age Group.")
    
    def __str__(self):
        return self.label
    
    class Meta:
        ordering = ['label']

class Audience(models.Model):
    """Specific segments like 'Entrepreneurs', 'Gen Z', etc."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(help_text="Context for the AI to understand this Age Group.")
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class VideoScriptParams(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=255)

    # Context
    niche = models.ForeignKey(Niche, on_delete=models.SET_NULL, null=True)
    sub_niche = models.ForeignKey(SubNiche, on_delete=models.SET_NULL, null=True)

    target_audiences = models.ManyToManyField(Audience, blank=True)
    age_groups = models.ManyToManyField(AgeGroup, blank=True)
    desired_tones = models.ManyToManyField(Tone, blank=True)
    visual_styles = models.ManyToManyField(Style, blank=True)

    # --- Media & References ---
    # The primary video reference (Visual/Vibe match)
    video_reference_url = models.URLField(
        blank=True, null=True, 
        help_text="A specific YouTube/TikTok link that captures the visual vibe you want."
    )

    # Specific instructions
    core_concept = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    

class ReferenceLink(models.Model):
    """
    Allows up to 3 informational links (articles, competitors, blogs).
    """
    project = models.ForeignKey(VideoScriptParams, on_delete=models.CASCADE, related_name="reference_links")
    url = models.URLField()
    
    def __str__(self):
        return self.url
    

class GeneratedScript(models.Model):
    """
    Stores the AI result. We separate this so we can have multiple
    versions (Draft 1, Draft 2) for a single Project if needed.
    """
    project = models.OneToOneField(VideoScriptParams, on_delete=models.CASCADE, related_name="script_output")
    
    # 1. Full Text (Plain text version for easy copying)
    full_script_content = models.TextField()

    # 2. Structured Data (For "Section Editing")
    # This stores the script as a JSON object, allowing the frontend to 
    # render editable "blocks" (Hook, Body, CTA).
    # Format: 
    # [
    #   {"section": "Hook", "content": "Did you know...", "visual_cue": "Face camera"},
    #   {"section": "Body", "content": "Here are 3 tips...", "visual_cue": "Show screen"},
    # ]
    script_sections = models.JSONField(default=list, blank=True)
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    is_finalized = models.BooleanField(default=False)

    def __str__(self):
        return f"Script for {self.project.title}"