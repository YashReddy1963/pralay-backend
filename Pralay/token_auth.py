"""
Custom authentication for handling both session and token authentication.
"""

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from users.models import RefreshToken
import hashlib

User = get_user_model()

class TokenAuthenticationMiddleware:
    """
    Custom middleware to handle token-based authentication
    for API endpoints that expect session authentication.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process API endpoints
        if request.path.startswith('/api/'):
            # Check for Authorization header with Bearer token
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user = self.authenticate_token(token)
                if user:
                    request.user = user
                    print(f"DEBUG: Token authentication successful for user: {user.email}")

        response = self.get_response(request)
        return response

    def authenticate_token(self, token):
        """
        Authenticate user using token.
        """
        try:
            # Look up the token in the database
            refresh_token = RefreshToken.objects.filter(
                token=token,
                is_revoked=False
            ).first()
            
            if refresh_token and refresh_token.is_valid():
                return refresh_token.user
                
        except Exception as e:
            print(f"DEBUG: Token authentication error: {e}")
            
        return None

def token_authenticate_user(request):
    """
    Authenticate user from Authorization: Bearer <token>.
    """
    auth_header = request.headers.get('Authorization', '')

    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1].strip()

        try:
            refresh_token = RefreshToken.objects.filter(
                token=token,
                is_revoked=False
            ).first()

            if refresh_token and refresh_token.is_valid():
                return refresh_token.user

        except Exception as e:
            print(f"Token authentication error: {e}")

    return None