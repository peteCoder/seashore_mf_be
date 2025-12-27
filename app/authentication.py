"""
Custom JWT Authentication Middleware
Supports both HTTP-only cookies and Authorization header
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that reads tokens from HTTP-only cookies
    Falls back to Authorization header if cookie not present
    
    This provides maximum security by:
    1. Using HTTP-only cookies (prevents XSS attacks)
    2. Supporting traditional Bearer token auth (for API clients)
    3. Validating tokens against JWT blacklist
    """
    
    def authenticate(self, request):
        """
        Try to authenticate user from cookie first, then from header
        """
        # Priority 1: Try to get token from HTTP-only cookie
        raw_token = request.COOKIES.get('access_token')
        
        # Priority 2: If not in cookie, try Authorization header
        if not raw_token:
            header = self.get_header(request)
            if header is None:
                return None
            
            try:
                raw_token = self.get_raw_token(header)
            except Exception:
                return None
        
        if raw_token is None:
            return None
        
        try:
            # Validate the token
            validated_token = self.get_validated_token(raw_token)
            
            # Get user from validated token
            user = self.get_user(validated_token)
            
            # Additional security checks
            if not user.is_active:
                raise AuthenticationFailed('User account is disabled.')
            
            if not user.is_approved:
                raise AuthenticationFailed('User account is pending approval.')
            
            return (user, validated_token)
            
        except (InvalidToken, TokenError) as e:
            # Token is invalid or expired
            return None
        except AuthenticationFailed:
            # Re-raise authentication failures
            raise


class OptionalCookieJWTAuthentication(CookieJWTAuthentication):
    """
    Same as CookieJWTAuthentication but doesn't fail if no token is present
    Useful for endpoints that support both authenticated and anonymous access
    """
    
    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return None
        



        