from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def update_platform(request):
    platform_id = request.POST.get('platform_id')
    if platform_id:
        request.session['selected_platform_id'] = platform_id
    
    # "HX-Refresh: true" tells HTMX to reload the whole page
    # This ensures the dashboard content matches the new platform selection.
    return HttpResponse(status=204, headers={'HX-Refresh': 'true'})