from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, 
    Branch, 
    ClientProfile, 
    StaffProfile, 
    NextOfKin,
    Guarantor,
)
import cloudinary.uploader


class BranchSerializer(serializers.ModelSerializer):
    """Serializer for Branch model"""
    
    class Meta:
        model = Branch
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state',
            'phone', 'email', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BranchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating branches (Admin only)"""
    
    class Meta:
        model = Branch
        fields = ['name', 'code', 'address', 'city', 'state', 'phone', 'email', 'is_active']
    
    def validate_code(self, value):
        """Ensure branch code is unique"""
        if Branch.objects.filter(code=value).exists():
            raise serializers.ValidationError("Branch code already exists.")
        return value.upper()


# ============================================
# ✅ SINGLE UNIFIED CLIENT REGISTRATION SERIALIZER
# ============================================

class ClientRegistrationSerializer(serializers.ModelSerializer):
    """
    Complete serializer for creating client users with ALL required fields.
    This replaces both ClientRegistrationSerializer and ClientCreateSerializer.
    """
    
    # Basic client profile fields
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.ChoiceField(
        choices=ClientProfile._meta.get_field('gender').choices,
        required=True
    )
    
    # ✅ COMPLETE Address Information (ALL REQUIRED)
    address = serializers.CharField(required=True)
    city = serializers.CharField(required=True)
    state = serializers.CharField(required=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    
    # ID Verification
    id_type = serializers.ChoiceField(
        choices=ClientProfile._meta.get_field('id_type').choices,
        required=True
    )
    id_number = serializers.CharField(required=True)
    
    # ✅ Employment & Financial Information (ALL INCLUDED)
    occupation = serializers.CharField(required=False, allow_blank=True)
    employer = serializers.CharField(required=False, allow_blank=True)
    monthly_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    
    # ✅ Banking Details (ALL INCLUDED)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    bvn = serializers.CharField(required=False, allow_blank=True)
    
    # Branch and staff assignment
    assigned_staff_id = serializers.UUIDField(required=False, allow_null=True)
    branch_id = serializers.UUIDField(required=True)
    
    # Password (optional)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    # ✅ Guarantor 1 (Required)
    guarantor1_name = serializers.CharField(required=True)
    guarantor1_phone = serializers.CharField(required=True)
    guarantor1_email = serializers.EmailField(required=False, allow_blank=True)
    guarantor1_relationship = serializers.CharField(required=True)
    guarantor1_address = serializers.CharField(required=True)
    guarantor1_occupation = serializers.CharField(required=False, allow_blank=True)
    guarantor1_employer = serializers.CharField(required=False, allow_blank=True)
    guarantor1_monthly_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    
    # ✅ Guarantor 2 (Optional - for loans)
    guarantor2_name = serializers.CharField(required=False, allow_blank=True)
    guarantor2_phone = serializers.CharField(required=False, allow_blank=True)
    guarantor2_email = serializers.EmailField(required=False, allow_blank=True)
    guarantor2_relationship = serializers.CharField(required=False, allow_blank=True)
    guarantor2_address = serializers.CharField(required=False, allow_blank=True)
    guarantor2_occupation = serializers.CharField(required=False, allow_blank=True)
    guarantor2_employer = serializers.CharField(required=False, allow_blank=True)
    guarantor2_monthly_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    
    # ✅ Next of Kin (Required)
    nok_name = serializers.CharField(required=True)
    nok_phone = serializers.CharField(required=True)
    nok_email = serializers.EmailField(required=False, allow_blank=True)
    nok_relationship = serializers.CharField(required=True)
    nok_address = serializers.CharField(required=True)
    nok_occupation = serializers.CharField(required=False, allow_blank=True)
    nok_employer = serializers.CharField(required=False, allow_blank=True)
    
    # Loan fields (Optional)
    loan_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    loan_duration = serializers.IntegerField(required=False, allow_null=True)
    loan_purpose = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            # User fields
            'email', 'first_name', 'last_name', 'phone', 'password',
            
            # Personal Information
            'date_of_birth', 'gender',
            
            # Address (COMPLETE)
            'address', 'city', 'state', 'postal_code',
            
            # ID Verification
            'id_type', 'id_number',
            
            # Employment & Financial
            'occupation', 'employer', 'monthly_income',
            
            # Banking Details
            'bank_name', 'account_number', 'bvn',
            
            # Assignment
            'assigned_staff_id', 'branch_id',
            
            # Guarantor 1
            'guarantor1_name', 'guarantor1_phone', 'guarantor1_email',
            'guarantor1_relationship', 'guarantor1_address',
            'guarantor1_occupation', 'guarantor1_employer', 'guarantor1_monthly_income',
            
            # Guarantor 2
            'guarantor2_name', 'guarantor2_phone', 'guarantor2_email',
            'guarantor2_relationship', 'guarantor2_address',
            'guarantor2_occupation', 'guarantor2_employer', 'guarantor2_monthly_income',
            
            # Next of Kin
            'nok_name', 'nok_phone', 'nok_email',
            'nok_relationship', 'nok_address',
            'nok_occupation', 'nok_employer',
            
            # Loan fields
            'loan_amount', 'loan_duration', 'loan_purpose',
        ]
    
    def validate_branch_id(self, value):
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist.")
        return value
    
    def validate_assigned_staff_id(self, value):
        if value:
            try:
                User.objects.get(id=value, user_role='staff')
            except User.DoesNotExist:
                raise serializers.ValidationError("Staff member does not exist.")
        return value
    
    def create(self, validated_data):
        """Create client user with profile and related data - COMPLETE IMPLEMENTATION"""
        
        # ✅ Extract ALL client profile fields
        client_profile_data = {
            'date_of_birth': validated_data.pop('date_of_birth'),
            'gender': validated_data.pop('gender'),
            'address': validated_data.pop('address'),
            'city': validated_data.pop('city'),
            'state': validated_data.pop('state'),
            'postal_code': validated_data.pop('postal_code', ''),
            'id_type': validated_data.pop('id_type'),
            'id_number': validated_data.pop('id_number'),
            'occupation': validated_data.pop('occupation', ''),
            'employer': validated_data.pop('employer', ''),
            'monthly_income': validated_data.pop('monthly_income', None),
            'bank_name': validated_data.pop('bank_name', ''),
            'account_number': validated_data.pop('account_number', ''),
            'bvn': validated_data.pop('bvn', ''),
        }
        
        # ✅ Extract guarantor 1 fields (COMPLETE)
        guarantor1_data = {
            'name': validated_data.pop('guarantor1_name'),
            'phone': validated_data.pop('guarantor1_phone'),
            'email': validated_data.pop('guarantor1_email', ''),
            'relationship': validated_data.pop('guarantor1_relationship'),
            'address': validated_data.pop('guarantor1_address'),
            'occupation': validated_data.pop('guarantor1_occupation', ''),
            'employer': validated_data.pop('guarantor1_employer', ''),
            'monthly_income': validated_data.pop('guarantor1_monthly_income', None),
        }
        
        # ✅ Extract guarantor 2 fields (COMPLETE)
        guarantor2_data = {
            'name': validated_data.pop('guarantor2_name', ''),
            'phone': validated_data.pop('guarantor2_phone', ''),
            'email': validated_data.pop('guarantor2_email', ''),
            'relationship': validated_data.pop('guarantor2_relationship', ''),
            'address': validated_data.pop('guarantor2_address', ''),
            'occupation': validated_data.pop('guarantor2_occupation', ''),
            'employer': validated_data.pop('guarantor2_employer', ''),
            'monthly_income': validated_data.pop('guarantor2_monthly_income', None),
        }
        
        # ✅ Extract NOK fields (COMPLETE)
        nok_data = {
            'name': validated_data.pop('nok_name'),
            'phone': validated_data.pop('nok_phone'),
            'email': validated_data.pop('nok_email', ''),
            'relationship': validated_data.pop('nok_relationship'),
            'address': validated_data.pop('nok_address'),
            'occupation': validated_data.pop('nok_occupation', ''),
            'employer': validated_data.pop('nok_employer', ''),
        }
        
        # Extract loan fields
        loan_amount = validated_data.pop('loan_amount', None)
        loan_duration = validated_data.pop('loan_duration', None)
        loan_purpose = validated_data.pop('loan_purpose', '')
        
        # Get assigned staff and branch
        assigned_staff_id = validated_data.pop('assigned_staff_id', None)
        branch_id = validated_data.pop('branch_id')
        password = validated_data.pop('password', None)
        
        # ✅ Create user
        if password:
            user = User.objects.create_user(
                user_role='client',
                branch_id=branch_id,
                is_approved=False,
                password=password,
                **validated_data
            )
        else:
            user = User.objects.create_user(
                user_role='client',
                branch_id=branch_id,
                is_approved=False,
                password=None,
                **validated_data
            )
        
        # ✅ Add branch and staff to profile data
        client_profile_data['branch_id'] = branch_id
        if assigned_staff_id:
            client_profile_data['assigned_staff_id'] = assigned_staff_id
        
        # Add loan info to notes if provided
        if loan_amount:
            client_profile_data['notes'] = f"""=== LOAN REQUEST ===
                Amount: ₦{loan_amount:,.2f}
                Duration: {loan_duration} months
                Purpose: {loan_purpose}
            """
        
        # ✅ Create client profile with ALL fields
        client_profile, created = ClientProfile.objects.update_or_create(
            user=user,
            defaults=client_profile_data
        )
        
        # ✅ Create Guarantor 1
        if guarantor1_data['name']:
            Guarantor.objects.create(client=user, **guarantor1_data)
        
        # ✅ Create Guarantor 2 (if provided)
        if guarantor2_data['name']:
            Guarantor.objects.create(client=user, **guarantor2_data)
        
        # ✅ Create Next of Kin
        if nok_data['name']:
            NextOfKin.objects.create(client=user, **nok_data)
        
        return user


# ============================================
# ✅ CLIENT PROFILE SERIALIZER WITH CLOUDINARY URLS
# ============================================

class ClientProfileSerializer(serializers.ModelSerializer):
    """Serializer for Client Profile with full Cloudinary URLs"""
    
    assigned_staff_name = serializers.CharField(source='assigned_staff.get_full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    loan_limit = serializers.SerializerMethodField()
    
    # ✅ Cloudinary URLs (not public_ids)
    profile_picture_url = serializers.SerializerMethodField()
    id_card_front_url = serializers.SerializerMethodField()
    id_card_back_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ClientProfile
        fields = [
            'id', 'level', 'has_set_password', 'date_of_birth', 'gender',
            'address', 'city', 'state', 'postal_code', 'country',
            'id_type', 'id_number',
            'occupation', 'employer', 'monthly_income',
            'account_number', 'bank_name', 'bvn',
            'credit_score', 'risk_rating',
            'assigned_staff', 'assigned_staff_name',
            'branch', 'branch_name',
            'profile_picture_url', 'id_card_front_url', 'id_card_back_url',
            'notes', 'loan_limit', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'loan_limit']
    
    def get_loan_limit(self, obj):
        return obj.get_loan_limit()
    
    def get_profile_picture_url(self, obj):
        """Return full Cloudinary URL"""
        if obj.profile_picture:
            return obj.profile_picture.url
        return None
    
    def get_id_card_front_url(self, obj):
        """Return full Cloudinary URL"""
        if obj.id_card_front:
            return obj.id_card_front.url
        return None
    
    def get_id_card_back_url(self, obj):
        """Return full Cloudinary URL"""
        if obj.id_card_back:
            return obj.id_card_back.url
        return None


# ============================================
# ✅ USER SERIALIZER WITH COMPLETE PROFILE DATA
# ============================================

# class UserSerializer(serializers.ModelSerializer):
#     """Serializer for User model with complete profile data"""
    
#     branch_name = serializers.CharField(source='branch.name', read_only=True)
#     full_name = serializers.CharField(source='get_full_name', read_only=True)
#     profile = serializers.SerializerMethodField()

#     # Add staff_profile as writable nested field
#     staff_profile = serializers.SerializerMethodField()

    
#     class Meta:
#         model = User
#         fields = [
#             'id', 'email', 'first_name', 'last_name', 'full_name',
#             'phone', 'user_role', 'branch', 'branch_name',
#             'is_approved', 'is_active', 'last_login',
#             'profile',
#             'created_at', 'updated_at',
#             'staff_profile',
#         ]
#         read_only_fields = ['id', 'created_at', 'updated_at', 'last_login']
    
#     def get_profile(self, obj):
#         """Get complete profile data based on user role"""
#         if obj.user_role == 'client':
#             try:
#                 profile = obj.client_profile
                
#                 # Get guarantors and NOK
#                 guarantors = obj.guarantors.all()
                
#                 try:
#                     next_of_kin = obj.next_of_kin
#                     nok_data = {
#                         'id': str(next_of_kin.id),
#                         'name': next_of_kin.name,
#                         'phone': next_of_kin.phone,
#                         'email': next_of_kin.email or '',
#                         'relationship': next_of_kin.relationship,
#                         'address': next_of_kin.address,
#                         'occupation': next_of_kin.occupation or '',
#                         'employer': next_of_kin.employer or '',
#                     }
#                 except NextOfKin.DoesNotExist:
#                     nok_data = None
                
#                 return {
#                     # Level and Loan Limit
#                     'level': profile.level,
#                     'loan_limit': float(profile.get_loan_limit()),
                    
#                     # Personal Information
#                     'date_of_birth': profile.date_of_birth,
#                     'gender': profile.gender,
                    
#                     # Address (COMPLETE)
#                     'address': profile.address,
#                     'city': profile.city,
#                     'state': profile.state,
#                     'postal_code': profile.postal_code or '',
#                     'country': profile.country,
                    
#                     # ID Verification
#                     'id_type': profile.id_type,
#                     'id_number': profile.id_number,
                    
#                     # Employment & Financial
#                     'occupation': profile.occupation or '',
#                     'employer': profile.employer or '',
#                     'monthly_income': float(profile.monthly_income) if profile.monthly_income else None,
                    
#                     # Banking Details
#                     'bank_name': profile.bank_name or '',
#                     'account_number': profile.account_number or '',
#                     'bvn': profile.bvn or '',
                    
#                     # Credit & Risk
#                     'credit_score': profile.credit_score,
#                     'risk_rating': profile.risk_rating,
                    
#                     # ✅ Cloudinary URLs (FULL URLS)
#                     'profile_picture_url': profile.profile_picture.url if profile.profile_picture else None,
#                     'id_card_front_url': profile.id_card_front.url if profile.id_card_front else None,
#                     'id_card_back_url': profile.id_card_back.url if profile.id_card_back else None,
                    
#                     # Account Status
#                     'has_set_password': profile.has_set_password,
                    
#                     # Staff Assignment
#                     'assigned_staff': profile.assigned_staff.get_full_name() if profile.assigned_staff else None,
#                     'assigned_staff_id': str(profile.assigned_staff.id) if profile.assigned_staff else None,
                    
#                     # Branch
#                     'branch_id': str(profile.branch.id) if profile.branch else None,
#                     'branch_name': profile.branch.name if profile.branch else None,
                    
#                     # ✅ Guarantors (COMPLETE)
#                     'guarantors': [
#                         {
#                             'id': str(g.id),
#                             'name': g.name,
#                             'phone': g.phone,
#                             'email': g.email or '',
#                             'relationship': g.relationship,
#                             'address': g.address,
#                             'occupation': g.occupation or '',
#                             'employer': g.employer or '',
#                             'monthly_income': float(g.monthly_income) if g.monthly_income else None,
#                             'id_type': g.id_type or '',
#                             'id_number': g.id_number or '',
#                         }
#                         for g in guarantors
#                     ],
                    
#                     # ✅ Next of Kin (COMPLETE)
#                     'next_of_kin': nok_data,
                    
#                     # Metadata
#                     'notes': profile.notes or '',
#                     'created_at': profile.created_at,
#                     'updated_at': profile.updated_at,
#                 }
#             except ClientProfile.DoesNotExist:
#                 return None
        
#         elif obj.user_role in ['staff', 'manager', 'director', 'admin']:
#             try:
#                 profile = obj.staff_profile
#                 return {
#                     'employee_id': profile.employee_id,
#                     'designation': profile.designation,
#                     'department': profile.department,
#                     'hire_date': profile.hire_date,
#                     'date_of_birth': profile.date_of_birth,
#                     'gender': profile.gender,
#                     'can_approve_loans': profile.can_approve_loans,
#                     'max_approval_amount': float(profile.max_approval_amount) if profile.max_approval_amount else None,
#                 }
#             except StaffProfile.DoesNotExist:
#                 return None
        
#         return None


# ============================================
# OTHER SERIALIZERS (Login, Password, etc.)
# ============================================

class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate credentials and user status"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")
        
        # Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")
        
        # Check if user is client
        if user.user_role == 'client':
            try:
                client_profile = user.client_profile
                if not client_profile.has_set_password:
                    raise serializers.ValidationError(
                        "Client access is not yet available. Please wait for the mobile app."
                    )
            except ClientProfile.DoesNotExist:
                raise serializers.ValidationError("Client profile not found.")
        
        # Authenticate
        user = authenticate(email=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        
        # Check if user is approved
        if not user.is_approved:
            raise serializers.ValidationError(
                "Your account is pending approval. Please contact the administrator."
            )
        
        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError(
                "Your account has been deactivated. Please contact the administrator."
            )
        
        attrs['user'] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_old_password(self, value):
        """Validate old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, attrs):
        """Validate new passwords match"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "New passwords do not match."
            })
        return attrs
    
    def save(self, **kwargs):
        """Change password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ClientPasswordSetSerializer(serializers.Serializer):
    """Serializer for client to set password for first time"""
    
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate passwords match and token is valid"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Passwords do not match."
            })
        
        # Validate token
        token = attrs.get('token')
        try:
            client_profile = ClientProfile.objects.get(password_reset_token=token)
            
            if not client_profile.is_token_valid(token):
                raise serializers.ValidationError({
                    "token": "Invalid or expired token."
                })
            
            attrs['client_profile'] = client_profile
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError({
                "token": "Invalid token."
            })
        
        return attrs
    
    def save(self, **kwargs):
        """Set password for client"""
        client_profile = self.validated_data['client_profile']
        user = client_profile.user
        
        # Set password
        user.set_password(self.validated_data['password'])
        user.save()
        
        # Update client profile
        client_profile.has_set_password = True
        client_profile.password_reset_token = None
        client_profile.password_reset_expires = None
        client_profile.save()
        
        return user