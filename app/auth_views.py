"""
Enhanced Authentication Views
Implements HTTP-only cookie-based JWT authentication with security features
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from datetime import timedelta

from .models import User, ClientProfile, StaffProfile, Notification
from .serializers import (
    LoginSerializer,
   
    PasswordChangeSerializer,
    ClientPasswordSetSerializer,
)

from .auth_serializers import (
     UserSerializer,
)


from .auth_serializers import (
RegisterSerializer,
    ClientCreateSerializer,
)

class RegisterView(generics.CreateAPIView):
    """
    Register new staff, manager, director, or admin user
    Public endpoint - no authentication required
    User created with is_approved=False (needs admin approval)
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create notification for admin
        admin_users = User.objects.filter(user_role='admin', is_active=True)
        for admin in admin_users:
            Notification.objects.create(
                user=admin,
                notification_type='staff_created',
                title='New Staff Registration',
                message=f'{user.get_full_name()} ({user.user_role}) has registered and awaits approval.',
                is_urgent=True
            )
        
        return Response({
            'success': True,
            'message': 'Registration successful. Your account is pending approval by an administrator.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name(),
                'user_role': user.user_role,
                'is_approved': user.is_approved,
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    Login user and return JWT tokens in HTTP-only cookies
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Get user data
        user_serializer = UserSerializer(user)
        
        # Create response
        response = Response({
            'success': True,
            'message': 'Login successful.',
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)
        
        # ✅ FIX: Use consistent SameSite based on environment
        samesite_setting = 'None' if not settings.DEBUG else 'Lax'
        secure_setting = not settings.DEBUG
        
        # Set HTTP-only cookies
        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=secure_setting,  # False in dev, True in prod
            samesite=samesite_setting,  # 'Lax' in dev, 'None' in prod
            max_age=3600,  # 1 hour
        )
        
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=secure_setting,
            samesite=samesite_setting,
            max_age=604800,  # 7 days
        )
        
        return response



class LogoutView(APIView):
    """Logout user by blacklisting refresh token and clearing cookies"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            
            if not refresh_token:
                refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return Response({
                    'success': False,
                    'message': 'Refresh token is required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            response = Response({
                'success': True,
                'message': 'Logout successful.'
            }, status=status.HTTP_200_OK)
            
            # ✅ FIX: Match login cookie settings
            samesite_setting = 'None' if not settings.DEBUG else 'Lax'
            
            response.delete_cookie('access_token', path='/', samesite=samesite_setting)
            response.delete_cookie('refresh_token', path='/', samesite=samesite_setting)
            
            return response
            
        except TokenError:
            response = Response({
                'success': True,
                'message': 'Logout successful.'
            }, status=status.HTTP_200_OK)
            
            samesite_setting = 'None' if not settings.DEBUG else 'Lax'
            response.delete_cookie('access_token', path='/', samesite=samesite_setting)
            response.delete_cookie('refresh_token', path='/', samesite=samesite_setting)
            
            return response
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Logout failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)





class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view that works with HTTP-only cookies"""
    
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            
            if not refresh_token:
                refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return Response({
                    'success': False,
                    'message': 'Refresh token not found.'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            request._full_data = {'refresh': refresh_token}
            response_data = super().post(request, *args, **kwargs)
            
            response = Response({
                'success': True,
                'message': 'Token refreshed successfully.',
            }, status=status.HTTP_200_OK)
            
            # ✅ FIX: Use consistent settings
            samesite_setting = 'None' if not settings.DEBUG else 'Lax'
            secure_setting = not settings.DEBUG
            
            response.set_cookie(
                key='access_token',
                value=response_data.data.get('access'),
                httponly=True,
                secure=secure_setting,
                samesite=samesite_setting,
                max_age=3600,
            )
            
            if 'refresh' in response_data.data:
                response.set_cookie(
                    key='refresh_token',
                    value=response_data.data.get('refresh'),
                    httponly=True,
                    secure=secure_setting,
                    samesite=samesite_setting,
                    max_age=604800,
                )
            
            return response
            
        except (TokenError, InvalidToken):
            return Response({
                'success': False,
                'message': 'Invalid or expired refresh token.'
            }, status=status.HTTP_401_UNAUTHORIZED)




class VerifyTokenView(APIView):
    """
    Verify if JWT token is valid
    Returns user data if token is valid
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        return Response({
            'success': True,
            'message': 'Token is valid.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name(),
                'user_role': user.user_role,
                'is_active': user.is_active,
                'is_approved': user.is_approved,
            }
        }, status=status.HTTP_200_OK)


class CurrentUserView(generics.RetrieveAPIView):
    """
    Get current authenticated user details with profile data
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'user': serializer.data
        }, status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    """
    Change password for authenticated user
    Requires old password for verification
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PasswordChangeSerializer
    
    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Password changed successfully. Please login again with your new password.'
        }, status=status.HTTP_200_OK)


class ClientPasswordSetView(APIView):
    """
    Set password for client user (first time)
    Uses token sent during client creation
    Public endpoint - no authentication required
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = ClientPasswordSetSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Password set successfully. You can now login with your credentials.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name(),
            }
        }, status=status.HTTP_200_OK)


class ClientPasswordResetRequestView(APIView):
    """
    Request password reset for client
    Generates new token and returns it
    In production, send token via email/SMS
    Public endpoint - no authentication required
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({
                'success': False,
                'message': 'Email is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email, user_role='client')
            client_profile = user.client_profile
            
            # Generate new token
            token = client_profile.generate_password_reset_token()
            
            # TODO: Send token via email/SMS in production
            # For now, return it in response (REMOVE IN PRODUCTION)
            
            return Response({
                'success': True,
                'message': 'Password reset token generated successfully. Check your email/SMS.',
                'token': token,  # Remove this in production
                'email': email
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Don't reveal if email exists (security best practice)
            return Response({
                'success': True,
                'message': 'If the email exists, a password reset token has been sent.',
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Password reset request failed.'
            }, status=status.HTTP_400_BAD_REQUEST)