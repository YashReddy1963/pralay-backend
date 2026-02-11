from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class TokenAuthenticationBackend(ModelBackend):
    """
    Custom authentication backend that handles Bearer token authentication
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Check for Bearer token in Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.info(f"TokenAuthenticationBackend: Found Bearer token: {token[:10]}...")
            
            # For now, we'll use a simple approach - if there's a token, 
            # we'll try to find the user by checking if they have a valid session
            # This is a temporary solution - in production, you'd want to implement
            # proper JWT token validation
            
            # Since we're using session-based auth, we'll rely on the session middleware
            # to handle the authentication
            return None
        
        # Fall back to default authentication
        return super().authenticate(request, username, password, **kwargs)

class SessionTokenAuthenticationBackend(ModelBackend):
    """
    Authentication backend that checks both session and token authentication
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First try session-based authentication
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(f"SessionTokenAuthenticationBackend: User {request.user.id} authenticated via session")
            return request.user
        
        # Check for Bearer token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.info(f"SessionTokenAuthenticationBackend: Found Bearer token: {token[:10]}...")
            
            # For now, we'll extract user info from the token or use a simple mapping
            # In a real implementation, you'd decode and validate the JWT token
            
            # Since we don't have proper JWT implementation, we'll use a workaround:
            # We'll check if there's a valid session and use that
            if hasattr(request, 'session') and request.session.session_key:
                # Try to get user from session
                user_id = request.session.get('_auth_user_id')
                if user_id:
                    try:
                        user = User.objects.get(id=user_id)
                        logger.info(f"SessionTokenAuthenticationBackend: Found user {user.id} from session")
                        return user
                    except User.DoesNotExist:
                        logger.warning(f"SessionTokenAuthenticationBackend: User {user_id} not found")
                        pass
        
        return None
