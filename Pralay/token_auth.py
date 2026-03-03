"""
Stateless token authentication for API endpoints.
Uses Bearer token from Authorization header; no session or CSRF.
"""

import logging
from django.contrib.auth import get_user_model
from users.models import RefreshToken

User = get_user_model()
logger = logging.getLogger(__name__)


def token_authenticate_user(request):
    """
    Authenticate user from Authorization: Bearer <token>.
    Token is the value stored in RefreshToken (same as returned at login).
    Returns the authenticated User or None.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if not auth_header:
        return None

    try:
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != 'Bearer':
            return None
        token = parts[1].strip()
        if not token:
            return None
    except (ValueError, AttributeError):
        return None

    try:
        refresh_token = RefreshToken.objects.filter(
            token=token,
            is_revoked=False
        ).first()

        if refresh_token and refresh_token.is_valid():
            return refresh_token.user
    except Exception as e:
        logger.warning("Token authentication error: %s", e)

    return None
