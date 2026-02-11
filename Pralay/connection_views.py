"""
Connection and service discovery views for QR code integration.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def connection_info(request):
    """
    Provides connection information for QR code integration.
    Returns frontend and backend URLs for service discovery.
    """
    try:
        # Get the request host for dynamic URL generation
        host = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        
        # Construct URLs
        base_url = f"{protocol}://{host}"
        
        # For development, use the configured URLs
        # In production, these would be dynamically determined
        connection_data = {
            'success': True,
            'frontend_url': 'http://172.16.82.20:8080',
            'backend_url': base_url,
            'api_base': f"{base_url}/api/",
            'services': {
                'auth': f"{base_url}/api/auth/",
                'hazard_reports': f"{base_url}/api/hazard-reports/",
                'verification': f"{base_url}/api/verify-image/",
                'video_verification': f"{base_url}/api/verify-video/"
            },
            'status': 'online',
            'version': '1.0.0'
        }
        
        logger.info(f"Connection info requested from {request.META.get('REMOTE_ADDR', 'unknown')}")
        
        return JsonResponse(connection_data)
        
    except Exception as e:
        logger.error(f"Error in connection_info: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Simple health check endpoint for service monitoring.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'Pralay Backend API',
        'timestamp': request.META.get('HTTP_DATE', 'unknown')
    })
