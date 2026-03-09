from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction

from apps.subscriptions.models import Subscriber
from apps.core.models import Notification
from apps.core.models import (
    Niche, Audience, AgeGroup, Tone, Style, 
    Generation, ReferenceLink, Region,
    VideoDuration, Outcome, Platform
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
        selected_duration = request.POST.get('duration')
        selected_platform = request.session.get('selected_platform_id')

        # M2M Data (returns lists of IDs)
        selected_audiences = request.POST.getlist('target_audiences')
        selected_ages = request.POST.getlist('age_groups')
        selected_tones = request.POST.getlist('desired_tones')
        selected_styles = request.POST.getlist('visual_styles')

        # Guard — ensure platform exists before proceeding
        if not selected_platform or not Platform.objects.filter(id=selected_platform).exists():
            messages.info(request, "Please select a platform in the top left before creating a project.")
            return redirect('create')

        try:
            with transaction.atomic():
                # 1. Create the main Project
                project = Generation.objects.create(
                    user=request.user,
                    title=title,
                    niche_id=niche_id,
                    platform_id=selected_platform,
                    sub_niche_id=sub_niche,
                    video_reference_url=video_ref,
                    core_concept=concept,
                    video_duration_id=selected_duration,
                    country_id=selected_country
                )

                # 2. Assign Many-to-Many relationships
                project.target_audiences.set(selected_audiences)
                project.age_groups.set(selected_ages)
                project.desired_tones.set(selected_tones)
                project.visual_styles.set(selected_styles)

                project.generate_hooks = 'gen_hooks' in request.POST
                project.generate_scripts = 'gen_scripts' in request.POST
                project.generate_cta = 'gen_cta' in request.POST

                # 3. Handle the 3 Reference URLs
                for i in range(1, 4):
                    url = request.POST.get(f'ref_url_{i}')
                    if url:
                        ReferenceLink.objects.create(project=project, url=url)

                project.save()
                messages.success(request, "Project was successfully created.")

                # 4. Trigger AI Generation (Next Step)
                # This is where you will call your Gemini API function
                # generate_and_save_script(project.id)

            return redirect('projects')
            
        except Exception as e:
            # Handle errors (e.g., add a message)
            messages.error(request, "Their was an error when creating your project. Please Contact Support to resolve the issue.")
            print(f"Error creating project: {e}")

    context = {
        'niches': Niche.objects.all(),
        'audiences': Audience.objects.all(),
        'ages': AgeGroup.objects.all(),
        'tones': Tone.objects.all(),
        'styles': Style.objects.all(),
        'countries': Region.objects.all(),
        'durations': VideoDuration.objects.all(),
        'outcomes': Outcome.objects.all(),
    }

    return render(request, "dashboard/pages/create.html", context)

@login_required
def projects(request):
    qs = Generation.objects.filter(user=request.user).select_related(
        'platform', 'niche', 'sub_niche', 'video_duration', 'country'
    ).prefetch_related(
        'target_audiences', 'age_groups', 'desired_tones', 'visual_styles', 'endgoal'
    )

    # Sorting
    sort = request.GET.get('sort', '-updated_at')
    sort_map = {
        '-modified': '-updated_at',
        '-created': '-created_at',
        'title': 'title',
    }
    qs = qs.order_by(sort_map.get(sort, '-updated_at'))

    # Search
    query = request.GET.get('q')
    if query:
        qs = qs.filter(title__icontains=query)

    # Platform filter
    platform_slug = request.GET.get('platform')
    if platform_slug:
        qs = qs.filter(platform__slug=platform_slug)

    context = {
        'projects': qs,
    }

    return render(request, 'dashboard/pages/library/projects.html', context)

@login_required
def user_templates(request):
    return render(request, 'dashboard/pages/library/templates.html')

@login_required
def user_generation_history(request):
    return render(request, 'dashboard/pages/library/history.html')

# TOOLS
@login_required
def studio(request):
    return render(request, 'dashboard/studio/index.html')

@login_required
def viral_breakdown_tool_view(request):
    return render(request, 'dashboard/pages/tools/viral_breakdown.html')

@login_required
def creator_spy_tool_view(request):
    return render(request, 'dashboard/pages/tools/creator_spy.html')

@login_required
def niche_insights_tool_view(request):
    return render(request, 'dashboard/pages/tools/niche_insights.html')

@login_required
def trend_intelligence_tool_view(request):
    return render(request, 'dashboard/pages/tools/trend_intelligence.html')

@login_required
def creator_calender_tool_view(request):
    return render(request, 'dashboard/pages/tools/calender.html')

@login_required
def seo_tool_view(request):
    return render(request, 'dashboard/pages/tools/seo.html')

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "dashboard/pages/notifications.html"
    context_object_name = "notifications"
    paginate_by = 10

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)\
            .select_related('content_type')\
            .prefetch_related('content_object')

        search_query = self.request.GET.get('q')
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) | 
                Q(message__icontains=search_query)
            )

        category = self.request.GET.get('category')
        valid_categories = Notification.NotificationChoices
        
        if category in valid_categories:
            qs = qs.filter(category=category)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.objects.filter(
            recipient=self.request.user, 
            is_read=False
        ).count()
        return context


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()

        if request.headers.get('HX-Request'):
            return JsonResponse({'status': 'success', 'message': 'Marked as read'})

        messages.success(request, "Notification marked as read.")
        # FIX: Redirect to the dashboard namespace
        return redirect('notifications')


class MarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        # FIX: Redirect to the dashboard namespace
        return redirect('notifications')


class DeleteNotificationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.delete()
        
        if request.headers.get('HX-Request'):
            return HttpResponse("") 

        messages.success(request, "Notification archived.")
        # FIX: Redirect to the dashboard namespace
        return redirect('notifications')