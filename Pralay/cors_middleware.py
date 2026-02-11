"""
Custom CORS middleware to ensure CORS headers are always present,
even for error responses.
"""
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

class CorsMiddleware:
    """
    Middleware to ensure CORS headers are always present in responses.
    This works alongside django-cors-headers to ensure headers are present
    even when errors occur.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add CORS headers if not already present
        origin = request.META.get('HTTP_ORIGIN')
        if origin:
            # Only add if not already set by django-cors-headers
            if 'Access-Control-Allow-Origin' not in response:
                response['Access-Control-Allow-Origin'] = origin
            if 'Access-Control-Allow-Credentials' not in response:
                response['Access-Control-Allow-Credentials'] = 'true'
            if 'Access-Control-Allow-Methods' not in response:
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            if 'Access-Control-Allow-Headers' not in response:
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
        
        return response

    def process_exception(self, request, exception):
        """
        Handle exceptions and ensure CORS headers are present in error responses.
        """
        logger.error(f"Exception in request: {str(exception)}", exc_info=True)
        
        # Create error response with CORS headers
        origin = request.META.get('HTTP_ORIGIN', '*')
        response = JsonResponse({
            'error': 'Internal server error',
            'message': str(exception) if hasattr(exception, '__str__') else 'An error occurred'
        }, status=500)
        
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
        
        return response
