# forms.py
from django import forms

class ContentCreationForm(forms.Form):
    topic = forms.CharField(label="Topic", max_length=100)
    niche = forms.CharField(label="Niche", max_length=100)
    
    AUDIENCE_CHOICES = [
        ('entrepreneurs', 'Entrepreneurs'),
        ('creators', 'Content Creators'),
        ('genz', 'Gen Z'),
        ('tech', 'Tech Enthusiasts'),
        ('students', 'Students'),
    ]
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, widget=forms.RadioSelect)
    
    AGE_CHOICES = [('13-17','13-17'), ('18-24','18-24'), ('25-34','25-34')]
    age_groups = forms.MultipleChoiceField(choices=AGE_CHOICES, widget=forms.CheckboxSelectMultiple)
    
    REGION_CHOICES = [('global', 'Multi-Regional'), ('us', 'United States'), ('uk', 'United Kingdom')]
    region = forms.ChoiceField(choices=REGION_CHOICES)
    
    DURATION_CHOICES = [('short', 'Short (<30s)'), ('standard', 'Standard (30-60s)'), ('long', 'Long (60s+)')]
    duration = forms.ChoiceField(choices=DURATION_CHOICES, widget=forms.RadioSelect)
    
    # These fields use the Custom JS Buttons in the template
    TONE_CHOICES = [('witty', 'Witty'), ('urgent', 'Urgent'), ('professional', 'Professional'), ('casual', 'Casual')]
    tone = forms.ChoiceField(choices=TONE_CHOICES)
    
    STYLE_CHOICES = [('fast', 'Fast-Paced'), ('minimal', 'Minimalist'), ('cinematic', 'Cinematic')]
    style = forms.ChoiceField(choices=STYLE_CHOICES)
    
    core_concept = forms.CharField(widget=forms.Textarea)
    
    OUTPUT_CHOICES = [('hooks', 'Generate Hooks'), ('script', 'Full Script'), ('cta', 'Call To Action')]
    output_options = forms.MultipleChoiceField(choices=OUTPUT_CHOICES, widget=forms.CheckboxSelectMultiple, initial=['hooks', 'script', 'cta'])