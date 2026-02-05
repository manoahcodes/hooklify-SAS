from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction

from apps.subscriptions.models import Subscriber
from apps.core.models import (
    Niche, Audience, AgeGroup, Tone, Style, 
    VideoScriptParams, ReferenceLink, Country
)

# Create your views here.

def _render_page(request, full_template, partial_template, context=None):
    context = context or {}
    if getattr(request, "htmx", False):
        return render(request, partial_template, context)
    return render(request, full_template, context)

@login_required
def dashboard(request):
    return render(request, 'dashboard/pages/dashboard.html')

@login_required
def ideas(request):
    return render(request, 'dashboard/pages/ideas.html')

@login_required
def create(request):
    if request.method == "POST":
        # Extract data from POST
        title = request.POST.get('title')
        niche_id = request.POST.get('niche')
        sub_niche = request.POST.get('sub_niche')
        video_ref = request.POST.get('video_reference_url')
        concept = request.POST.get('core_concept')
        selected_country = request.POST.get('target_country')

        # M2M Data (returns lists of IDs)
        selected_audiences = request.POST.getlist('target_audiences')
        selected_ages = request.POST.getlist('age_groups')
        selected_tones = request.POST.getlist('desired_tones')
        selected_styles = request.POST.getlist('visual_styles')

        try:
            with transaction.atomic():
                # 1. Create the main Project
                project = VideoScriptParams.objects.create(
                    user=request.user,
                    title=title,
                    niche_id=niche_id,
                    sub_niche=sub_niche,
                    video_reference_url=video_ref,
                    core_concept=concept
                )

                # 2. Assign Many-to-Many relationships
                project.target_audiences.set(selected_audiences)
                project.age_groups.set(selected_ages)
                project.desired_tones.set(selected_tones)
                project.visual_styles.set(selected_styles)

                # 3. Handle the 3 Reference URLs
                for i in range(1, 4):
                    url = request.POST.get(f'ref_url_{i}')
                    if url:
                        ReferenceLink.objects.create(project=project, url=url)

                # 4. Trigger AI Generation (Next Step)
                # This is where you will call your Gemini API function
                # generate_and_save_script(project.id)

            return redirect('dashboard:project_detail', pk=project.pk)
            
        except Exception as e:
            # Handle errors (e.g., add a message)
            print(f"Error creating project: {e}")

    context = {
        'niches': Niche.objects.all(),
        'audiences': Audience.objects.all(),
        'ages': AgeGroup.objects.all(),
        'tones': Tone.objects.all(),
        'styles': Style.objects.all(),
        'countries': Country.objects.all(),
    }

    return render(request, "dashboard/pages/create.html", context)

@login_required
def projects(request):
    return render(request, 'dashboard/pages/library/projects.html')

@login_required
def user_templates(request):
    return render(request, 'dashboard/pages/library/templates.html')

@login_required
def user_generation_history(request):
    return render(request, 'dashboard/pages/library/history.html')

@login_required
def studio(request):
    return render(request, 'dashboard/studio/index.html')
