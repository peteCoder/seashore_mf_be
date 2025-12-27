from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .models import User, Branch, ClientProfile
from .serializers import (
    ClientRegistrationSerializer,
    BranchSerializer, 
    BranchCreateSerializer,
   
)

from .auth_views import (
     UserSerializer,
)
import cloudinary.uploader
from .permissions import IsStaffOrAbove


class BranchListView(generics.ListAPIView):
    """List all active branches (public endpoint for registration)"""
    queryset = Branch.objects.filter(is_active=True)
    serializer_class = BranchSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'success': True,
            'branches': serializer.data
        }, status=status.HTTP_200_OK)


class BranchCreateView(generics.CreateAPIView):
    """Create new branch (Admin only)"""
    queryset = Branch.objects.all()
    serializer_class = BranchCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        if request.user.user_role != 'admin':
            return Response({
                'success': False,
                'message': 'Only administrators can create branches.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Branch created successfully.',
            'branch': BranchSerializer(branch).data
        }, status=status.HTTP_201_CREATED)


class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete branch (Admin only for update/delete)"""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'branch': serializer.data
        }, status=status.HTTP_200_OK)
    
    def update(self, request, *args, **kwargs):
        if request.user.user_role != 'admin':
            return Response({
                'success': False,
                'message': 'Only administrators can update branches.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'success': True,
            'message': 'Branch updated successfully.',
            'branch': serializer.data
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        if request.user.user_role != 'admin':
            return Response({
                'success': False,
                'message': 'Only administrators can delete branches.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        
        return Response({
            'success': True,
            'message': 'Branch deactivated successfully.'
        }, status=status.HTTP_200_OK)


# ============================================
# ✅ FIXED CLIENT CREATE VIEW
# ============================================

class ClientCreateView(generics.CreateAPIView):
    """
    API endpoint for creating client accounts (Staff+ only)
    ✅ FIXED: Properly handles all fields and returns complete user data
    """
    serializer_class = ClientRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffOrAbove]
    
    def create(self, request, *args, **kwargs):
        """Create client with proper error handling"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # ✅ Return complete serialized user data with profile
            user_serializer = UserSerializer(user)
            
            return Response(
                {
                    'success': True,
                    'message': 'Client created successfully',
                    'data': user_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            # Log the error
            import traceback
            traceback.print_exc()
            
            # Return detailed error response
            return Response(
                {
                    'success': False,
                    'error': str(e),
                    'detail': 'Failed to create client account'
                },
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================
# ✅ FIXED IMAGE UPLOAD VIEW
# ============================================

class ClientImageUploadView(APIView):
    """
    API endpoint for uploading client images to Cloudinary
    ✅ FIXED: Properly uploads to Cloudinary and stores public_ids
    """
    
    permission_classes = [permissions.IsAuthenticated, IsStaffOrAbove]
    parser_classes = [MultiPartParser, FormParser]  # ✅ REQUIRED for file uploads
    
    def post(self, request, client_id):
        try:
            # ✅ Get client
            try:
                client = User.objects.get(id=client_id, user_role='client')
                profile = client.client_profile
            except User.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": "Client not found"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            except ClientProfile.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": "Client profile not found"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # ✅ Get uploaded files from request
            profile_image = request.FILES.get('profile_image')
            id_front_image = request.FILES.get('id_front_image')
            id_back_image = request.FILES.get('id_back_image')
            
            uploaded_images = {}
            
            # ✅ Upload profile image to Cloudinary
            if profile_image:
                try:
                    result = cloudinary.uploader.upload(
                        profile_image,
                        folder='clients/profile_pictures',
                        transformation={
                            'width': 400,
                            'height': 400,
                            'crop': 'fill',
                            'gravity': 'face',
                            'quality': 'auto',
                            'fetch_format': 'auto'
                        }
                    )
                    # ✅ Save public_id to CloudinaryField
                    profile.profile_picture = result['public_id']
                    uploaded_images['profile_picture'] = result['secure_url']
                except Exception as e:
                    return Response(
                        {
                            "success": False,
                            "error": f"Failed to upload profile image: {str(e)}"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # ✅ Upload ID front to Cloudinary
            if id_front_image:
                try:
                    result = cloudinary.uploader.upload(
                        id_front_image,
                        folder='clients/id_cards/front',
                        transformation={
                            'quality': 'auto',
                            'fetch_format': 'auto'
                        }
                    )
                    # ✅ Save public_id to CloudinaryField
                    profile.id_card_front = result['public_id']
                    uploaded_images['id_card_front'] = result['secure_url']
                except Exception as e:
                    return Response(
                        {
                            "success": False,
                            "error": f"Failed to upload ID front: {str(e)}"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # ✅ Upload ID back to Cloudinary
            if id_back_image:
                try:
                    result = cloudinary.uploader.upload(
                        id_back_image,
                        folder='clients/id_cards/back',
                        transformation={
                            'quality': 'auto',
                            'fetch_format': 'auto'
                        }
                    )
                    # ✅ Save public_id to CloudinaryField
                    profile.id_card_back = result['public_id']
                    uploaded_images['id_card_back'] = result['secure_url']
                except Exception as e:
                    return Response(
                        {
                            "success": False,
                            "error": f"Failed to upload ID back: {str(e)}"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # ✅ Save profile with updated images
            profile.save()
            
            # ✅ Refresh to get CloudinaryField URLs
            profile.refresh_from_db()
            
            return Response({
                "success": True,
                "message": "Images uploaded successfully",
                "uploaded_images": uploaded_images,
                "client_id": str(client.id),
                # ✅ Return full URLs for frontend
                "profile_picture_url": profile.profile_picture.url if profile.profile_picture else None,
                "id_card_front_url": profile.id_card_front.url if profile.id_card_front else None,
                "id_card_back_url": profile.id_card_back.url if profile.id_card_back else None,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {
                    "success": False,
                    "error": str(e),
                    "detail": "Failed to upload images"
                },
                status=status.HTTP_400_BAD_REQUEST
            )