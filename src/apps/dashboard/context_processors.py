from apps.core.models import Platform

def platform_context(request):
    # Fetch all platforms (cached by Django after the first query in a request)
    platforms = Platform.objects.all()
    
    # Get selection from session or default to the first platform
    selected_id = request.session.get('selected_platform_id')
    selected_platform = next((p for p in platforms if str(p.id) == str(selected_id)), platforms.first())
    
    return {
        'platforms': platforms,
        'selected_platform': selected_platform
    }