from django.db import models
from apps.core.models import Generation

class Project(models.Model):
    """
    Stores the AI result. We separate this so we can have multiple
    versions (Draft 1, Draft 2) for a single Project if needed.
    """
    project = models.OneToOneField(Generation, on_delete=models.CASCADE, related_name="projects")
    
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
