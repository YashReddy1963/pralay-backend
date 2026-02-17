"""
Token-based authentication for API endpoints.
Stateless; no session or CSRF.
"""

from django.http import JsonResponse
from functools import wraps
from Pralay.token_auth import token_authenticate_user


def token_required(view_func):
    """Decorator: require valid Bearer token; set request.user."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = token_authenticate_user(request)
        if not user:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        request.user = user
        return view_func(request, *args, **kwargs)
    return wrapper


class TokenRequiredMixin:
    """Mixin for class-based views: require Bearer token; set request.user in dispatch."""
    def dispatch(self, request, *args, **kwargs):
        user = token_authenticate_user(request)
        if not user:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        request.user = user
        return super().dispatch(request, *args, **kwargs)
