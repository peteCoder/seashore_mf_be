"""
User Management Views
Complete CRUD operations for clients and staff management
"""
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

from .models import User, ClientProfile, Notification, Guarantor, NextOfKin, Branch
from .auth_serializers import (
    UserSerializer,
)
from .permissions import (
    IsAdmin,
    IsManagerOrAbove,
    IsStaffOrAbove,
)
from rest_framework.permissions import IsAuthenticated


from rest_framework import status, generics, permissions
from rest_framework.parsers import MultiPartParser, FormParser
from .models import User
from .auth_serializers import StaffRegistrationSerializer
import cloudinary.uploader



class UserListView(generics.ListAPIView):
    """
    List all users (filtered based on role)
    Staff: See only users in their branch
    Manager: See only users in their branch
    Director/Admin: See all users
    """
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin and Director can see all users
        if user.user_role in ['admin', 'director']:
            queryset = User.objects.all()
        else:
            # Manager and Staff can only see users in their branch
            queryset = User.objects.filter(branch=user.branch)
        
        # Apply filters from query params
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(user_role=role)
        
        is_approved = self.request.query_params.get('is_approved')
        if is_approved is not None:
            queryset = queryset.filter(is_approved=is_approved.lower() == 'true')
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        
        return queryset.select_related('branch').prefetch_related(
            'client_profile', 'staff_profile'
        ).order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'users': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'users': serializer.data
        }, status=status.HTTP_200_OK)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update user details
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Permission check
        if not self._can_access_user(request.user, instance):
            return Response({
                'success': False,
                'message': 'You do not have permission to view this user.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    def _can_access_user(self, requesting_user, target_user):
        """Check if requesting user can access target user"""
        
        # Admin and Director can access all users
        if requesting_user.user_role in ['admin', 'director']:
            return True
        
        # Manager can access users in their branch
        if requesting_user.user_role == 'manager':
            return target_user.branch == requesting_user.branch
        
        # Staff can access clients in their branch
        if requesting_user.user_role == 'staff':
            if target_user.user_role == 'client':
                return target_user.branch == requesting_user.branch
            return False
        
        # Users can access their own profile
        return requesting_user.id == target_user.id


class UserApprovalView(APIView):
    """
    Approve or reject user registration (Admin only)
    """
    permission_classes = [IsAdmin]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        action = request.data.get('action')  # 'approve' or 'reject'
        
        if action == 'approve':
            user.is_approved = True
            user.is_active = True
            user.save()
            
            # Notify user
            Notification.objects.create(
                user=user,
                notification_type='client_approved' if user.user_role == 'client' else 'staff_created',
                title='Account Approved',
                message='Your account has been approved. You can now login and access the system.',
                is_urgent=True
            )
            
            message = f'User {user.get_full_name()} approved successfully.'
            
        elif action == 'reject':
            user.is_approved = False
            user.is_active = False
            user.save()
            
            # Notify user
            Notification.objects.create(
                user=user,
                notification_type='client_rejected',
                title='Account Rejected',
                message='Your account registration has been rejected. Please contact support for more information.',
                is_urgent=True
            )
            
            message = f'User {user.get_full_name()} rejected.'
            
        else:
            return Response({
                'success': False,
                'message': 'Invalid action. Use "approve" or "reject".'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': message,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class UserActivationView(APIView):
    """
    Activate or deactivate user (Manager/Director/Admin only)
    """
    permission_classes = [IsManagerOrAbove]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Manager can only activate/deactivate users in their branch
        if request.user.user_role == 'manager':
            if user.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only activate/deactivate users in your branch.'
                }, status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action')  # 'activate' or 'deactivate'
        
        if action == 'activate':
            user.is_active = True
            user.save()
            message = f'User {user.get_full_name()} activated successfully.'
            
        elif action == 'deactivate':
            user.is_active = False
            user.save()
            
            # Notify user
            Notification.objects.create(
                user=user,
                notification_type='staff_deactivated',
                title='Account Deactivated',
                message='Your account has been deactivated. Please contact your manager for more information.'
            )
            
            message = f'User {user.get_full_name()} deactivated successfully.'
            
        else:
            return Response({
                'success': False,
                'message': 'Invalid action. Use "activate" or "deactivate".'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': message,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)



class ClientListView(generics.ListAPIView):
    """
    API endpoint for listing clients
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Disable pagination to avoid double-wrapping
    
    def get_queryset(self):
        """Filter clients based on user role and branch"""
        user = self.request.user
        queryset = User.objects.filter(user_role='client').select_related(
            'branch', 
            'client_profile', 
            'client_profile__assigned_staff',
            'next_of_kin'  # OneToOne uses select_related
        ).prefetch_related(
            'guarantors'  # ForeignKey (reverse) uses prefetch_related
        )
        
        # Branch isolation for non-admin users
        if user.user_role in ['staff', 'manager', 'director']:
            queryset = queryset.filter(branch=user.branch)
        
        # Apply filters
        is_active = self.request.query_params.get('is_active')
        is_approved = self.request.query_params.get('is_approved')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if is_approved is not None:
            queryset = queryset.filter(is_approved=is_approved.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Custom list method to return proper response format"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'success': True,
            'clients': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)



# Add this to your StaffListView in user_management_views.py (around line 280)

class StaffListView(generics.ListAPIView):
    """
    List all staff with filtering and search
    """
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    
    def get_queryset(self):
        user = self.request.user
        
        # ✅ FIXED: Add role filter support
        role_filter = self.request.query_params.get('role')
        
        # Base queryset
        if user.user_role in ['admin', 'director']:
            if role_filter:
                # ✅ Filter by specific role (e.g., role=staff)
                queryset = User.objects.filter(user_role=role_filter)
            else:
                # Show all staff roles
                queryset = User.objects.filter(user_role__in=['staff', 'manager', 'director', 'admin'])
        else:
            if role_filter:
                # ✅ Filter by specific role in user's branch
                queryset = User.objects.filter(
                    user_role=role_filter,
                    branch=user.branch
                )
            else:
                # Show staff and managers in branch
                queryset = User.objects.filter(
                    user_role__in=['staff', 'manager'],
                    branch=user.branch
                )
        
        # Apply other filters (status, search, etc.)
        status_filter = self.request.query_params.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'suspended':
            queryset = queryset.filter(is_active=False, is_approved=True)
        elif status_filter == 'deactivated':
            queryset = queryset.filter(is_active=False)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(staff_profile__employee_id__icontains=search)
            )
        
        return queryset.select_related('branch', 'staff_profile').order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get counts for stats
        total_staff = queryset.count()
        active_staff = queryset.filter(is_active=True).count()
        suspended_staff = queryset.filter(is_active=False, is_approved=True).count()
        deactivated_staff = queryset.filter(is_active=False).count()
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'success': True,
                'stats': {
                    'total': total_staff,
                    'active': active_staff,
                    'suspended': suspended_staff,
                    'deactivated': deactivated_staff
                },
                'staff': serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'stats': {
                'total': total_staff,
                'active': active_staff,
                'suspended': suspended_staff,
                'deactivated': deactivated_staff
            },
            'staff': serializer.data
        }, status=status.HTTP_200_OK)


class AssignClientToStaffView(APIView):
    """
    Assign client to staff member (Manager and above)
    """
    permission_classes = [IsManagerOrAbove]
    
    def post(self, request, client_id):
        try:
            client = User.objects.get(id=client_id, user_role='client')
            client_profile = client.client_profile
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Client not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        except ClientProfile.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Client profile not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        staff_id = request.data.get('staff_id')
        
        if not staff_id:
            # Unassign client
            old_staff = client_profile.assigned_staff
            client_profile.assigned_staff = None
            client_profile.save()
            
            if old_staff:
                Notification.objects.create(
                    user=old_staff,
                    notification_type='assignment_changed',
                    title='Client Unassigned',
                    message=f'{client.get_full_name()} has been unassigned from you.',
                    related_client=client
                )
            
            return Response({
                'success': True,
                'message': 'Client unassigned successfully.'
            }, status=status.HTTP_200_OK)
        
        try:
            staff = User.objects.get(id=staff_id, user_role='staff')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Staff member not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if manager is assigning within their branch
        if request.user.user_role == 'manager':
            if client.branch != request.user.branch or staff.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only assign clients and staff within your branch.'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Assign client
        old_staff = client_profile.assigned_staff
        client_profile.assigned_staff = staff
        client_profile.save()
        
        # Notify new staff
        Notification.objects.create(
            user=staff,
            notification_type='assignment_changed',
            title='New Client Assigned',
            message=f'{client.get_full_name()} has been assigned to you.',
            related_client=client
        )
        
        # Notify old staff if exists
        if old_staff and old_staff != staff:
            Notification.objects.create(
                user=old_staff,
                notification_type='assignment_changed',
                title='Client Reassigned',
                message=f'{client.get_full_name()} has been reassigned to {staff.get_full_name()}.',
                related_client=client
            )
        
        return Response({
            'success': True,
            'message': f'Client assigned to {staff.get_full_name()} successfully.',
            'client': UserSerializer(client).data
        }, status=status.HTTP_200_OK)
    



# 🔧 FIXED: StaffUpdateView - Accepts both snake_case and camelCase field names

from decimal import Decimal, InvalidOperation
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


class StaffUpdateView(APIView):
    """
    Update staff member details
    Manager and above can update staff in their branch
    Admin/Director can update any staff
    
    Accepts both snake_case and camelCase field names for compatibility
    """
    permission_classes = [IsManagerOrAbove]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def patch(self, request, staff_id):
        try:
            staff = User.objects.get(id=staff_id, user_role__in=['staff', 'manager', 'director', 'admin'])
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Staff member not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Permission check
        if request.user.user_role == 'manager':
            if staff.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only update staff in your branch.'
                }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Helper function to get value from either snake_case or camelCase
        def get_field(snake_case, camel_case=None):
            if camel_case is None:
                parts = snake_case.split('_')
                camel_case = parts[0] + ''.join(word.capitalize() for word in parts[1:])
            return data.get(snake_case) or data.get(camel_case)
        
        # ============================================
        # Update basic user fields
        # ============================================
        
        first_name = get_field('first_name', 'firstName')
        if first_name:
            staff.first_name = first_name
        
        last_name = get_field('last_name', 'lastName')
        if last_name:
            staff.last_name = last_name
        
        email = data.get('email')
        if email:
            staff.email = email
        
        phone = get_field('phone', 'phoneNumber') or data.get('phone')
        if phone:
            staff.phone = phone
        
        # Update user role if provided
        user_role = get_field('user_role', 'userRole')
        if user_role and user_role in ['staff', 'manager', 'director', 'admin']:
            staff.user_role = user_role
        
        # Update branch if provided
        branch_id = get_field('branch', 'branch')
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
                staff.branch = branch
            except Branch.DoesNotExist:
                pass
        
        staff.save()
        
        # ============================================
        # Update staff profile
        # ============================================
        
        if hasattr(staff, 'staff_profile'):
            profile = staff.staff_profile
            
            # ----- Personal Information -----
            
            date_of_birth = get_field('date_of_birth', 'dateOfBirth')
            if date_of_birth:
                profile.date_of_birth = date_of_birth
            
            gender = data.get('gender')
            if gender:
                profile.gender = gender
            
            address = get_field('address', 'homeAddress')
            if address is not None:
                profile.address = address
            
            blood_group = get_field('blood_group', 'bloodGroup')
            if blood_group:
                profile.blood_group = blood_group
            
            # ----- Employment Details -----
            
            employee_id = get_field('employee_id', 'employeeId')
            if employee_id:
                profile.employee_id = employee_id
            
            designation = get_field('designation', 'role')
            if designation:
                profile.designation = designation
            
            department = data.get('department')
            if department:
                profile.department = department
            
            hire_date = get_field('hire_date', 'hireDate')
            if hire_date:
                profile.hire_date = hire_date
            
            # Handle salary
            salary = data.get('salary')
            if salary and str(salary).strip():
                try:
                    profile.salary = Decimal(str(salary))
                except (ValueError, InvalidOperation):
                    return Response({
                        'success': False,
                        'message': 'Invalid salary value. Please enter a valid number.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # ----- Banking Details -----
            
            bank_name = get_field('bank_name', 'bankName')
            if bank_name is not None:
                profile.bank_name = bank_name
            
            bank_account = get_field('bank_account', 'accountNumber')
            if bank_account is not None:
                profile.bank_account = bank_account
            
            # ----- Emergency Contact -----
            
            emergency_contact_name = get_field('emergency_contact_name', 'emergencyContactName')
            if emergency_contact_name is not None:
                profile.emergency_contact_name = emergency_contact_name
            
            emergency_contact_phone = get_field('emergency_contact_phone', 'emergencyContactPhone')
            if emergency_contact_phone is not None:
                profile.emergency_contact_phone = emergency_contact_phone
            
            emergency_contact_relationship = get_field('emergency_contact_relationship', 'emergencyContactRelationship')
            if emergency_contact_relationship is not None:
                profile.emergency_contact_relationship = emergency_contact_relationship
            
            # ----- ID Information -----
            
            id_type = get_field('id_type', 'idType')
            if id_type is not None:
                profile.id_type = id_type
            
            id_number = get_field('id_number', 'idNumber')
            if id_number is not None:
                profile.id_number = id_number
            
            # ----- Image Uploads -----
            
            # Profile picture
            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']
            elif 'profileImage' in request.FILES:
                profile.profile_picture = request.FILES['profileImage']
            
            # ID Card Front
            if 'id_card_front' in request.FILES:
                profile.id_card_front = request.FILES['id_card_front']
            elif 'idCardFront' in request.FILES:
                profile.id_card_front = request.FILES['idCardFront']
            
            # ID Card Back
            if 'id_card_back' in request.FILES:
                profile.id_card_back = request.FILES['id_card_back']
            elif 'idCardBack' in request.FILES:
                profile.id_card_back = request.FILES['idCardBack']
            
            profile.save()
        
        # Notify staff about profile update
        Notification.objects.create(
            user=staff,
            notification_type='system_alert',
            title='Profile Updated',
            message=f'Your profile has been updated by {request.user.get_full_name()}.'
        )
        
        return Response({
            'success': True,
            'message': 'Staff updated successfully.',
            'staff': UserSerializer(staff).data
        }, status=status.HTTP_200_OK)


class StaffCreateView(generics.CreateAPIView):
    """
    API endpoint for creating staff accounts (Manager+ only)
    Similar to client creation - supports optional password
    """
    serializer_class = StaffRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    parser_classes = [MultiPartParser, FormParser]
    
    def create(self, request, *args, **kwargs):
        """Create staff with proper error handling"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # ✅ FIXED: Let Django-Cloudinary handle the upload automatically
            # Handle profile image upload if provided
            if 'profileImage' in request.FILES:
                try:
                    # Save directly to the staff profile - CloudinaryField handles upload
                    profile = user.staff_profile
                    profile.profile_picture = request.FILES['profileImage']
                    profile.save()
                except Exception as e:
                    # Don't fail the entire request if image upload fails
                    print(f"Image upload warning: {str(e)}")
            
            # Return complete serialized user data with profile
            user_serializer = UserSerializer(user)
            
            return Response(
                {
                    'success': True,
                    'message': 'Staff created successfully',
                    'data': user_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            # Log the error
            import traceback
            traceback.print_exc()
            
            # Return detailed error response
            error_detail = str(e)
            if hasattr(e, 'detail'):
                error_detail = e.detail
            
            return Response(
                {
                    'success': False,
                    'error': error_detail,
                    'detail': 'Failed to create staff account'
                },
                status=status.HTTP_400_BAD_REQUEST
            )



# ============================================
# CLIENT DETAIL/UPDATE/DELETE VIEWS
# ============================================

class ClientDetailView(generics.RetrieveAPIView):
    """
    Retrieve detailed client information
    Staff can view clients in their branch
    Manager+ can view clients in their branch
    Admin/Director can view all clients
    """
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        
        # ✅ CORRECT: Guarantors and NextOfKin are related to User, not ClientProfile!
        queryset = User.objects.filter(user_role='client').select_related(
            'branch', 
            'client_profile',
            'client_profile__assigned_staff',
            'next_of_kin'  # ✅ OneToOneField - use select_related
        ).prefetch_related(
            'guarantors'   # ✅ ForeignKey with related_name='guarantors'
        )
        
        # Branch isolation
        if user.user_role not in ['admin', 'director']:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            return Response({
                'success': True,
                'client': serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ClientUpdateView(generics.UpdateAPIView):
    """
    Update client information
    Staff can update clients in their branch
    Manager+ can update clients in their branch
    Admin/Director can update all clients
    """
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(user_role='client').select_related(
            'branch', 'client_profile'
        )
        
        # Branch isolation
        if user.user_role not in ['admin', 'director']:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset
    
    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', True)  # Allow partial updates
            instance = self.get_object()
            
            # Update basic user fields
            if 'first_name' in request.data:
                instance.first_name = request.data.get('first_name')
            if 'last_name' in request.data:
                instance.last_name = request.data.get('last_name')
            if 'email' in request.data:
                instance.email = request.data.get('email')
            if 'phone' in request.data:
                instance.phone = request.data.get('phone')
            
            instance.save()
            
            # Update client profile
            if hasattr(instance, 'client_profile'):
                profile = instance.client_profile
                
                # Personal info
                if 'date_of_birth' in request.data:
                    profile.date_of_birth = request.data.get('date_of_birth')
                if 'gender' in request.data:
                    profile.gender = request.data.get('gender')
                
                # Address
                if 'address' in request.data:
                    profile.address = request.data.get('address')
                if 'city' in request.data:
                    profile.city = request.data.get('city')
                if 'state' in request.data:
                    profile.state = request.data.get('state')
                if 'postal_code' in request.data:
                    profile.postal_code = request.data.get('postal_code')
                
                # ID verification
                if 'id_type' in request.data:
                    profile.id_type = request.data.get('id_type')
                if 'id_number' in request.data:
                    profile.id_number = request.data.get('id_number')
                
                # Employment
                if 'occupation' in request.data:
                    profile.occupation = request.data.get('occupation')
                if 'employer' in request.data:
                    profile.employer = request.data.get('employer')
                if 'monthly_income' in request.data:
                    profile.monthly_income = request.data.get('monthly_income')
                
                # Banking
                if 'bank_name' in request.data:
                    profile.bank_name = request.data.get('bank_name')
                if 'account_number' in request.data:
                    profile.account_number = request.data.get('account_number')
                if 'bvn' in request.data:
                    profile.bvn = request.data.get('bvn')
                
                profile.save()
            
            # Notify client
            Notification.objects.create(
                user=instance,
                notification_type='system_alert',
                title='Profile Updated',
                message=f'Your profile has been updated by {request.user.get_full_name()}.'
            )
            
            serializer = self.get_serializer(instance)
            return Response({
                'success': True,
                'message': 'Client updated successfully',
                'client': serializer.data
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ClientDeleteView(generics.DestroyAPIView):
    """
    Delete (deactivate) client
    Only Manager+ can delete clients
    """
    permission_classes = [IsManagerOrAbove]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(user_role='client')
        
        # Branch isolation
        if user.user_role not in ['admin', 'director']:
            queryset = queryset.filter(branch=user.branch)
        
        return queryset
    
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Soft delete - deactivate instead of deleting
            instance.is_active = False
            instance.is_approved = False
            instance.save()
            
            # Notify client
            Notification.objects.create(
                user=instance,
                notification_type='client_rejected',
                title='Account Deactivated',
                message='Your account has been deactivated. Please contact support for more information.',
                is_urgent=True
            )
            
            return Response({
                'success': True,
                'message': f'Client {instance.get_full_name()} deactivated successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)


# ============================================
# STAFF DETAIL/UPDATE/DELETE VIEWS
# ============================================

class StaffDetailView(generics.RetrieveAPIView):
    """
    Retrieve detailed staff information
    Staff can view themselves
    Manager can view staff in their branch
    Admin/Director can view all staff
    """
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrAbove]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(
            user_role__in=['staff', 'manager', 'director', 'admin']
        ).select_related('branch', 'staff_profile')
        
        # Branch isolation
        if user.user_role not in ['admin', 'director']:
            queryset = queryset.filter(
                Q(id=user.id) | Q(branch=user.branch)
            )
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            # Get assigned clients for staff members
            assigned_clients = []
            if instance.user_role in ['staff', 'manager']:
                clients = User.objects.filter(
                    user_role='client',
                    client_profile__assigned_staff=instance
                ).select_related('branch', 'client_profile')
                
                assigned_clients = [{
                    'id': str(client.id),
                    'full_name': client.get_full_name(),
                    'email': client.email,
                    'phone': client.phone or '',
                    'level': getattr(client.client_profile, 'level', 'level_1') if hasattr(client, 'client_profile') else 'level_1',
                    'is_active': client.is_active,
                    'branch_name': client.branch.name if client.branch else 'N/A',
                    'created_at': client.created_at.isoformat() if client.created_at else None,
                } for client in clients]
            
            return Response({
                'success': True,
                'staff': serializer.data,
                'assigned_clients': assigned_clients,
                'assigned_clients_count': len(assigned_clients)
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Staff member not found'
            }, status=status.HTTP_404_NOT_FOUND)


# StaffUpdateView already exists in your code
# StaffDeleteView below

class StaffDeleteView(generics.DestroyAPIView):
    """
    Delete (deactivate) staff member
    Only Admin can delete staff
    """
    permission_classes = [IsAdmin]
    lookup_field = 'id'
    
    def get_queryset(self):
        return User.objects.filter(
            user_role__in=['staff', 'manager', 'director']
        )
    
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Prevent deleting yourself
            if instance.id == request.user.id:
                return Response({
                    'success': False,
                    'error': 'You cannot delete your own account'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Soft delete - deactivate
            instance.is_active = False
            instance.save()
            
            # Notify staff
            Notification.objects.create(
                user=instance,
                notification_type='staff_deactivated',
                title='Account Deactivated',
                message='Your account has been deactivated. Please contact your administrator.',
                is_urgent=True
            )
            
            return Response({
                'success': True,
                'message': f'Staff member {instance.get_full_name()} deactivated successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Staff member not found'
            }, status=status.HTTP_404_NOT_FOUND)


# ============================================
# GUARANTOR VIEWS
# ============================================

class GuarantorListCreateView(APIView):
    """
    List all guarantors for a client or add a new one
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request, client_id):
        """List all guarantors for a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        guarantors = client.guarantors.all()
        guarantor_data = [
            {
                'id': str(g.id),
                'name': g.name,
                'phone': g.phone,
                'email': g.email or '',
                'relationship': g.relationship,
                'address': g.address,
                'occupation': g.occupation or '',
                'employer': g.employer or '',
                'monthly_income': float(g.monthly_income) if g.monthly_income else None,
                'id_type': g.id_type or '',
                'id_number': g.id_number or '',
                'created_at': g.created_at,
            }
            for g in guarantors
        ]
        
        return Response({
            'success': True,
            'guarantors': guarantor_data
        }, status=status.HTTP_200_OK)
    
    def post(self, request, client_id):
        """Add a new guarantor to a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check for non-admin/director
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'You can only add guarantors to clients in your branch'
                }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'phone', 'relationship', 'address']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'error': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create guarantor
        guarantor = Guarantor.objects.create(
            client=client,
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email', ''),
            relationship=data.get('relationship'),
            address=data.get('address'),
            occupation=data.get('occupation', ''),
            employer=data.get('employer', ''),
            monthly_income=data.get('monthly_income'),
            id_type=data.get('id_type', ''),
            id_number=data.get('id_number', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Guarantor added successfully',
            'guarantor': {
                'id': str(guarantor.id),
                'name': guarantor.name,
                'phone': guarantor.phone,
                'email': guarantor.email or '',
                'relationship': guarantor.relationship,
                'address': guarantor.address,
                'occupation': guarantor.occupation or '',
                'employer': guarantor.employer or '',
                'monthly_income': float(guarantor.monthly_income) if guarantor.monthly_income else None,
            }
        }, status=status.HTTP_201_CREATED)


class GuarantorDetailView(APIView):
    """
    Update or delete a specific guarantor
    """
    permission_classes = [IsStaffOrAbove]
    
    def patch(self, request, client_id, guarantor_id):
        """Update a guarantor"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            guarantor = Guarantor.objects.get(id=guarantor_id, client=client)
        except Guarantor.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Guarantor not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Update fields if provided
        if 'name' in data:
            guarantor.name = data['name']
        if 'phone' in data:
            guarantor.phone = data['phone']
        if 'email' in data:
            guarantor.email = data['email']
        if 'relationship' in data:
            guarantor.relationship = data['relationship']
        if 'address' in data:
            guarantor.address = data['address']
        if 'occupation' in data:
            guarantor.occupation = data['occupation']
        if 'employer' in data:
            guarantor.employer = data['employer']
        if 'monthly_income' in data:
            guarantor.monthly_income = data['monthly_income']
        if 'id_type' in data:
            guarantor.id_type = data['id_type']
        if 'id_number' in data:
            guarantor.id_number = data['id_number']
        
        guarantor.save()
        
        return Response({
            'success': True,
            'message': 'Guarantor updated successfully',
            'guarantor': {
                'id': str(guarantor.id),
                'name': guarantor.name,
                'phone': guarantor.phone,
                'email': guarantor.email or '',
                'relationship': guarantor.relationship,
                'address': guarantor.address,
            }
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, client_id, guarantor_id):
        """Delete a guarantor"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            guarantor = Guarantor.objects.get(id=guarantor_id, client=client)
        except Guarantor.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Guarantor not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        guarantor.delete()
        
        return Response({
            'success': True,
            'message': 'Guarantor deleted successfully'
        }, status=status.HTTP_200_OK)


# ============================================
# NEXT OF KIN VIEWS
# ============================================

class NextOfKinView(APIView):
    """
    Get, create, update, or delete next of kin for a client
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request, client_id):
        """Get next of kin for a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            nok = client.next_of_kin
            return Response({
                'success': True,
                'next_of_kin': {
                    'id': str(nok.id),
                    'name': nok.name,
                    'phone': nok.phone,
                    'email': nok.email or '',
                    'relationship': nok.relationship,
                    'address': nok.address,
                    'occupation': nok.occupation or '',
                    'employer': nok.employer or '',
                }
            }, status=status.HTTP_200_OK)
        except NextOfKin.DoesNotExist:
            return Response({
                'success': True,
                'next_of_kin': None
            }, status=status.HTTP_200_OK)
    
    def post(self, request, client_id):
        """Create or replace next of kin for a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'phone', 'relationship', 'address']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'error': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete existing NOK if exists
        try:
            existing_nok = client.next_of_kin
            existing_nok.delete()
        except NextOfKin.DoesNotExist:
            pass
        
        # Create new NOK
        nok = NextOfKin.objects.create(
            client=client,
            name=data.get('name'),
            phone=data.get('phone'),
            email=data.get('email', ''),
            relationship=data.get('relationship'),
            address=data.get('address'),
            occupation=data.get('occupation', ''),
            employer=data.get('employer', ''),
        )
        
        return Response({
            'success': True,
            'message': 'Next of kin added successfully',
            'next_of_kin': {
                'id': str(nok.id),
                'name': nok.name,
                'phone': nok.phone,
                'email': nok.email or '',
                'relationship': nok.relationship,
                'address': nok.address,
            }
        }, status=status.HTTP_201_CREATED)
    
    def patch(self, request, client_id):
        """Update next of kin for a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            nok = client.next_of_kin
        except NextOfKin.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Next of kin not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        
        # Update fields if provided
        if 'name' in data:
            nok.name = data['name']
        if 'phone' in data:
            nok.phone = data['phone']
        if 'email' in data:
            nok.email = data['email']
        if 'relationship' in data:
            nok.relationship = data['relationship']
        if 'address' in data:
            nok.address = data['address']
        if 'occupation' in data:
            nok.occupation = data['occupation']
        if 'employer' in data:
            nok.employer = data['employer']
        
        nok.save()
        
        return Response({
            'success': True,
            'message': 'Next of kin updated successfully',
            'next_of_kin': {
                'id': str(nok.id),
                'name': nok.name,
                'phone': nok.phone,
                'email': nok.email or '',
                'relationship': nok.relationship,
                'address': nok.address,
            }
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, client_id):
        """Delete next of kin for a client"""
        try:
            client = User.objects.get(id=client_id, user_role='client')
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Client not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            nok = client.next_of_kin
        except NextOfKin.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Next of kin not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Branch check
        if request.user.user_role not in ['admin', 'director']:
            if client.branch != request.user.branch:
                return Response({
                    'success': False,
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        nok.delete()
        
        return Response({
            'success': True,
            'message': 'Next of kin deleted successfully'
        }, status=status.HTTP_200_OK)