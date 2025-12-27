"""
Enhanced Serializers for Authentication
Includes account lockout, validation, and comprehensive user data
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from datetime import timedelta
from .models import User, ClientProfile, StaffProfile, Branch, Guarantor, NextOfKin

# ✅ ADD THIS LINE
from decimal import Decimal, InvalidOperation

class BranchSerializer(serializers.ModelSerializer):
    """Serializer for Branch model"""
    
    class Meta:
        model = Branch
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state',
            'phone', 'email', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BranchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating branches"""
    
    class Meta:
        model = Branch
        fields = [
            'name', 'code', 'address', 'city', 'state',
            'phone', 'email'
        ]
    
    def validate_code(self, value):
        """Ensure branch code is unique"""
        if Branch.objects.filter(code=value).exists():
            raise serializers.ValidationError("Branch code already exists.")
        return value.upper()


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with account lockout protection
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            raise serializers.ValidationError({
                'error': 'Email and password are required.'
            })
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'error': 'Invalid credentials.'
            })
        
        # Check if account is locked
        if user.account_locked_until and user.account_locked_until > timezone.now():
            remaining_minutes = int((user.account_locked_until - timezone.now()).seconds / 60)
            raise serializers.ValidationError({
                'error': f'Account locked due to multiple failed login attempts. Try again in {remaining_minutes} minutes.'
            })
        
        # Verify password
        if not user.check_password(password):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.account_locked_until = timezone.now() + timedelta(minutes=30)
                user.save(update_fields=['failed_login_attempts', 'account_locked_until'])
                raise serializers.ValidationError({
                    'error': 'Too many failed login attempts. Your account has been locked for 30 minutes.'
                })
            
            user.save(update_fields=['failed_login_attempts'])
            attempts_remaining = 5 - user.failed_login_attempts
            raise serializers.ValidationError({
                'error': f'Invalid credentials. {attempts_remaining} attempts remaining before account lockout.'
            })
        
        # Check if user is approved
        if not user.is_approved:
            raise serializers.ValidationError({
                'error': 'Your account is pending administrator approval. Please contact support.'
            })
        
        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError({
                'error': 'Your account has been deactivated. Please contact support.'
            })
        
        # For clients, check if password has been set
        if user.user_role == 'client':
            try:
                if not user.client_profile.has_set_password:
                    raise serializers.ValidationError({
                        'error': 'Please set your password using the link provided during account creation.'
                    })
            except ClientProfile.DoesNotExist:
                raise serializers.ValidationError({
                    'error': 'Client profile not found. Please contact support.'
                })
        
        # Reset failed attempts on successful login
        if user.failed_login_attempts > 0 or user.account_locked_until:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.save(update_fields=['failed_login_attempts', 'account_locked_until'])
        
        data['user'] = user
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for staff, manager, director, admin registration
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    # Staff profile fields
    designation = serializers.CharField(required=True)
    department = serializers.ChoiceField(
        choices=StaffProfile._meta.get_field('department').choices,
        required=True
    )
    hire_date = serializers.DateField(required=True)
    salary = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False
    )
    address = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_relationship = serializers.CharField(required=False, allow_blank=True)
    bank_account = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    blood_group = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 'first_name', 'last_name',
            'phone', 'user_role', 'branch',
            # Staff profile fields
            'designation', 'department', 'hire_date', 'salary',
            'date_of_birth', 'gender', 'address',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
            'bank_account', 'bank_name', 'blood_group'
        ]
    
    def validate_user_role(self, value):
        """Ensure only staff roles can be registered"""
        if value not in ['staff', 'manager', 'director', 'admin']:
            raise serializers.ValidationError("Invalid user role for registration.")
        return value
    
    def validate(self, data):
        """Validate password confirmation"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        return data
    
    def validate_branch(self, value):
        """Ensure branch is required for non-admin roles"""
        user_role = self.initial_data.get('user_role')
        if user_role in ['staff', 'manager'] and not value:
            raise serializers.ValidationError("Branch is required for staff and managers.")
        return value
    
    def create(self, validated_data):
        # Remove password_confirm and staff profile fields
        validated_data.pop('password_confirm')
        designation = validated_data.pop('designation')
        department = validated_data.pop('department')
        hire_date = validated_data.pop('hire_date')
        salary = validated_data.pop('salary')
        date_of_birth = validated_data.pop('date_of_birth', None)
        gender = validated_data.pop('gender', '')
        address = validated_data.pop('address', '')
        emergency_contact_name = validated_data.pop('emergency_contact_name', '')
        emergency_contact_phone = validated_data.pop('emergency_contact_phone', '')
        emergency_contact_relationship = validated_data.pop('emergency_contact_relationship', '')
        bank_account = validated_data.pop('bank_account', '')
        bank_name = validated_data.pop('bank_name', '')
        blood_group = validated_data.pop('blood_group', '')
        
        # Create user (inactive until approved)
        user = User.objects.create_user(
            **validated_data,
            is_active=True,
            is_approved=False  # Requires admin approval
        )
        
        # Generate employee ID (8 digits)
        employee_id = f"{user.id.int % 100000000:08d}"
        
        # Create staff profile
        StaffProfile.objects.create(
            user=user,
            employee_id=employee_id,
            designation=designation,
            department=department,
            hire_date=hire_date,
            salary=salary,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship,
            bank_account=bank_account,
            bank_name=bank_name,
        )
        
        return user


class ClientCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating client users
    Clients are created by staff/manager/director/admin
    """
    # Client profile fields
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=True
    )
    address = serializers.CharField(required=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    id_type = serializers.ChoiceField(
        choices=ClientProfile._meta.get_field('id_type').choices,
        required=True
    )
    id_number = serializers.CharField(required=True)
    occupation = serializers.CharField(required=False, allow_blank=True)
    employer = serializers.CharField(required=False, allow_blank=True)
    monthly_income = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        required=False, allow_null=True
    )
    account_number = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    bvn = serializers.CharField(required=False, allow_blank=True)
    
    # Branch assignment
    branch_id = serializers.UUIDField(required=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone',
            'date_of_birth', 'gender', 'address', 'city', 'state', 'postal_code',
            'id_type', 'id_number', 'occupation', 'employer', 'monthly_income',
            'account_number', 'bank_name', 'bvn', 'branch_id'
        ]
    
    def create(self, validated_data):
        # Remove client profile fields
        branch_id = validated_data.pop('branch_id')
        date_of_birth = validated_data.pop('date_of_birth')
        gender = validated_data.pop('gender')
        address = validated_data.pop('address')
        city = validated_data.pop('city', '')
        state = validated_data.pop('state')
        postal_code = validated_data.pop('postal_code', '')
        id_type = validated_data.pop('id_type')
        id_number = validated_data.pop('id_number')
        occupation = validated_data.pop('occupation', '')
        employer = validated_data.pop('employer', '')
        monthly_income = validated_data.pop('monthly_income', None)
        account_number = validated_data.pop('account_number', '')
        bank_name = validated_data.pop('bank_name', '')
        bvn = validated_data.pop('bvn', '')
        
        # Get branch
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            raise serializers.ValidationError({'branch_id': 'Branch not found.'})
        
        # Create client user (no password - unusable)
        user = User.objects.create_user(
            **validated_data,
            user_role='client',
            branch=branch,
            is_active=True,
            is_approved=False  # Requires admin approval
        )
        user.set_unusable_password()
        user.save()
        
        # Create client profile
        ClientProfile.objects.create(
            user=user,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            id_type=id_type,
            id_number=id_number,
            occupation=occupation,
            employer=employer,
            monthly_income=monthly_income,
            account_number=account_number,
            bank_name=bank_name,
            bvn=bvn,
            branch=branch,
            level='bronze'  # Start at bronze level
        )
        
        return user




class StaffRegistrationSerializer(serializers.ModelSerializer):
    """
    Complete serializer for creating staff users with ALL required fields.
    Supports optional password (can be set later by staff).
    """
    
    # Password (optional - can be set later)
    password = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(
        write_only=True, 
        required=False, 
        allow_blank=True
    )
    
    # Staff profile fields
    designation = serializers.CharField(required=True)
    department = serializers.ChoiceField(
        choices=StaffProfile._meta.get_field('department').choices,
        required=True
    )
    hire_date = serializers.DateField(required=True)
    salary = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=True
    )
    
    # Personal Information
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False,
        allow_blank=True
    )
    address = serializers.CharField(required=False, allow_blank=True)
    blood_group = serializers.CharField(required=False, allow_blank=True)
    
    # Emergency Contact
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_relationship = serializers.CharField(required=False, allow_blank=True)
    
    # Bank Details
    bank_account = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    
    # Branch assignment
    branch_id = serializers.UUIDField(required=True)
    
    class Meta:
        model = User
        fields = [
            # User fields
            'email', 'first_name', 'last_name', 'phone', 'user_role',
            'password', 'password_confirm',
            
            # Staff profile fields
            'designation', 'department', 'hire_date', 'salary',
            
            # Personal Information
            'date_of_birth', 'gender', 'address', 'blood_group',
            
            # Emergency Contact
            'emergency_contact_name', 'emergency_contact_phone', 
            'emergency_contact_relationship',
            
            # Bank Details
            'bank_account', 'bank_name',
            
            # Branch
            'branch_id'
        ]
    
    def validate_user_role(self, value):
        """Ensure only staff roles can be registered"""
        if value not in ['staff', 'manager', 'director', 'admin']:
            raise serializers.ValidationError("Invalid user role for registration.")
        return value
    
    def validate_branch_id(self, value):
        """Ensure branch exists"""
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist.")
        return value
    
    def validate(self, data):
        """Validate password confirmation if password is provided"""
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        
        # If password is provided, confirm must match
        if password:
            if not password_confirm:
                raise serializers.ValidationError({
                    'password_confirm': 'Password confirmation is required when setting password.'
                })
            if password != password_confirm:
                raise serializers.ValidationError({
                    'password_confirm': 'Passwords do not match.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create staff user with profile - COMPLETE IMPLEMENTATION"""
        
        # Extract password fields
        password = validated_data.pop('password', None)
        validated_data.pop('password_confirm', None)
        
        # Extract staff profile fields
        designation = validated_data.pop('designation')
        department = validated_data.pop('department')
        hire_date = validated_data.pop('hire_date')
        salary = validated_data.pop('salary')
        date_of_birth = validated_data.pop('date_of_birth', None)
        gender = validated_data.pop('gender', '')
        address = validated_data.pop('address', '')
        blood_group = validated_data.pop('blood_group', '')
        emergency_contact_name = validated_data.pop('emergency_contact_name', '')
        emergency_contact_phone = validated_data.pop('emergency_contact_phone', '')
        emergency_contact_relationship = validated_data.pop('emergency_contact_relationship', '')
        bank_account = validated_data.pop('bank_account', '')
        bank_name = validated_data.pop('bank_name', '')
        
        # Get branch
        branch_id = validated_data.pop('branch_id')
        try:
            branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            raise serializers.ValidationError({'branch_id': 'Branch not found.'})
        
        # Create user
        if password:
            # Create with password
            user = User.objects.create_user(
                branch=branch,
                is_approved=False,  # Requires admin approval
                is_active=True,
                password=password,
                **validated_data
            )
        else:
            # Create without password (will be set later)
            user = User.objects.create_user(
                branch=branch,
                is_approved=False,
                is_active=True,
                password=None,
                **validated_data
            )
            user.set_unusable_password()
            user.save()
        
        # Generate employee ID (8 digits based on UUID)
        employee_id = f"{user.id.int % 100000000:08d}"
        
        # Create staff profile
        StaffProfile.objects.create(
            user=user,
            employee_id=employee_id,
            designation=designation,
            department=department,
            hire_date=hire_date,
            salary=salary,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            blood_group=blood_group,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship,
            bank_account=bank_account,
            bank_name=bank_name,
        )
        
        return user



class UserSerializer(serializers.ModelSerializer):
    """
    Comprehensive user serializer with complete profile data
    """
    full_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    assigned_clients_count = serializers.SerializerMethodField()  # ✅ NEW
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'user_role', 'branch', 'branch_name',
            'is_approved', 'is_active', 'last_login',
            'created_at', 'profile',
            'assigned_clients_count',  # ✅ NEW
        ]
        read_only_fields = ['id', 'created_at', 'last_login']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else None
    
    # ✅ NEW METHOD
    def get_assigned_clients_count(self, obj):
        """Get count of clients assigned to this staff member"""
        if obj.user_role == 'staff':
            return obj.assigned_clients.count()
        return 0
    
    def update(self, instance, validated_data):
        """Handle updates including nested staff profile"""
        
        # Update basic user fields
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()
        
        # Update staff profile if exists
        if hasattr(instance, 'staff_profile'):
            staff_profile = instance.staff_profile
            
            # Get request data
            request = self.context.get('request')
            if request and request.data:
                data = request.data
                
                # Update basic fields
                if 'dateOfBirth' in data and data.get('dateOfBirth'):
                    staff_profile.date_of_birth = data.get('dateOfBirth')
                
                if 'gender' in data and data.get('gender'):
                    staff_profile.gender = data.get('gender')
                
                if 'homeAddress' in data:
                    staff_profile.address = data.get('homeAddress') or ''
                
                if 'bloodGroup' in data and data.get('bloodGroup'):
                    staff_profile.blood_group = data.get('bloodGroup')
                
                if 'role' in data and data.get('role'):
                    staff_profile.designation = data.get('role')
                
                if 'department' in data and data.get('department'):
                    staff_profile.department = data.get('department')
                
                # ✅ Handle salary with empty string check
                if 'salary' in data:
                    salary_value = data.get('salary')
                    if salary_value and str(salary_value).strip():
                        try:
                            staff_profile.salary = Decimal(str(salary_value))
                        except (ValueError, InvalidOperation):
                            pass  # Keep existing value if invalid
                
                # Emergency contact
                if 'emergencyContactName' in data:
                    staff_profile.emergency_contact_name = data.get('emergencyContactName') or ''
                
                if 'emergencyContactRelationship' in data:
                    staff_profile.emergency_contact_relationship = data.get('emergencyContactRelationship') or ''
                
                if 'emergencyContactPhone' in data:
                    staff_profile.emergency_contact_phone = data.get('emergencyContactPhone') or ''
                
                # Bank details
                if 'bankName' in data:
                    staff_profile.bank_name = data.get('bankName') or ''
                
                if 'accountNumber' in data:
                    staff_profile.bank_account = data.get('accountNumber') or ''
                
                # Handle profile image upload
                if 'profileImage' in request.FILES:
                    staff_profile.profile_picture = request.FILES['profileImage']
                
                staff_profile.save()
        
        # ✅✅✅ CRITICAL: RETURN THE INSTANCE! ✅✅✅
        return instance
    


    def get_profile(self, obj):
        """Get complete profile data based on user role"""
        if obj.user_role == 'client':
            try:
                profile = obj.client_profile
                
                # ✅ Get guarantors (multiple)
                guarantors = obj.guarantors.all()
                
                # ✅ Get next of kin (one)
                try:
                    next_of_kin = obj.next_of_kin
                    nok_data = {
                        'id': str(next_of_kin.id),
                        'name': next_of_kin.name,
                        'phone': next_of_kin.phone,
                        'email': next_of_kin.email or '',
                        'relationship': next_of_kin.relationship,
                        'address': next_of_kin.address,
                        'occupation': next_of_kin.occupation or '',
                        'employer': next_of_kin.employer or '',
                    }
                except NextOfKin.DoesNotExist:
                    nok_data = None
                
                # ✅ FIXED: Handle profile picture safely
                profile_pic_url = None
                if profile.profile_picture:
                    try:
                        # Try to get URL (if it's a CloudinaryField)
                        profile_pic_url = profile.profile_picture.url
                    except AttributeError:
                        # If it's a string (public_id), build URL manually
                        if isinstance(profile.profile_picture, str):
                            from cloudinary.utils import cloudinary_url
                            profile_pic_url, _ = cloudinary_url(profile.profile_picture)
                
                return {
                    # ✅ Level and Loan Limit
                    'level': profile.level,
                    'loan_limit': float(profile.get_loan_limit()),
                    
                    # ✅ Personal Information (COMPLETE)
                    'date_of_birth': profile.date_of_birth,
                    'gender': profile.gender,
                    
                    # ✅ Address (ALL FIELDS)
                    'address': profile.address,
                    'city': profile.city,
                    'state': profile.state,
                    'postal_code': profile.postal_code or '',
                    'country': profile.country,
                    
                    # ✅ ID Verification
                    'id_type': profile.id_type,
                    'id_number': profile.id_number,
                    
                    # ✅ Employment & Financial Information
                    'occupation': profile.occupation or '',
                    'employer': profile.employer or '',
                    'monthly_income': float(profile.monthly_income) if profile.monthly_income else None,
                    
                    # ✅ Banking Details
                    'bank_name': profile.bank_name or '',
                    'account_number': profile.account_number or '',
                    'bvn': profile.bvn or '',
                    
                    # ✅ Credit & Risk
                    'credit_score': profile.credit_score,
                    'risk_rating': profile.risk_rating,
                    
                    # ✅ FIXED: Images from Cloudinary (SAFE ACCESS)
                    'profile_picture_url': profile_pic_url,
                    'id_card_front_url': profile.id_card_front.url if profile.id_card_front else None,
                    'id_card_back_url': profile.id_card_back.url if profile.id_card_back else None,
                    
                    # ✅ Account Status
                    'has_set_password': profile.has_set_password,
                    
                    # ✅ Staff Assignment
                    'assigned_staff': profile.assigned_staff.get_full_name() if profile.assigned_staff else None,
                    'assigned_staff_id': str(profile.assigned_staff.id) if profile.assigned_staff else None,
                    
                    # ✅ Branch
                    'branch_id': str(profile.branch.id) if profile.branch else None,
                    'branch_name': profile.branch.name if profile.branch else None,
                    
                    # ✅ Guarantors (STRUCTURED DATA - Multiple)
                    'guarantors': [
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
                        }
                        for g in guarantors
                    ],
                    
                    # ✅ Next of Kin (STRUCTURED DATA - Single)
                    'next_of_kin': nok_data,
                    
                    # ✅ Metadata
                    'notes': profile.notes or '',
                    'created_at': profile.created_at,
                    'updated_at': profile.updated_at,
                }
            except ClientProfile.DoesNotExist:
                return None
        
        elif obj.user_role in ['staff', 'manager', 'director', 'admin']:
            try:
                profile = obj.staff_profile
                
                # ✅ FIXED: Handle all images safely
                profile_pic_url = None
                if profile.profile_picture:
                    try:
                        profile_pic_url = profile.profile_picture.url
                    except AttributeError:
                        if isinstance(profile.profile_picture, str):
                            from cloudinary.utils import cloudinary_url
                            profile_pic_url, _ = cloudinary_url(profile.profile_picture)
                
                id_front_url = None
                if hasattr(profile, 'id_card_front') and profile.id_card_front:
                    try:
                        id_front_url = profile.id_card_front.url
                    except AttributeError:
                        pass
                
                id_back_url = None
                if hasattr(profile, 'id_card_back') and profile.id_card_back:
                    try:
                        id_back_url = profile.id_card_back.url
                    except AttributeError:
                        pass
                
                return {
                    # ✅ Employment Information
                    'employee_id': profile.employee_id,
                    'designation': profile.designation,
                    'department': profile.department,
                    'hire_date': profile.hire_date,
                    'termination_date': profile.termination_date,
                    'employment_status': profile.is_employment_active(),
                    
                    # ✅ Compensation
                    'salary': float(profile.salary) if profile.salary else 0,
                    'bank_account': profile.bank_account or '',
                    'bank_name': profile.bank_name or '',
                    
                    # ✅ Personal Information
                    'date_of_birth': profile.date_of_birth,
                    'gender': profile.gender or '',
                    'address': profile.address or '',
                    'blood_group': getattr(profile, 'blood_group', '') or '',
                    
                    # ✅ Emergency Contact
                    'emergency_contact_name': profile.emergency_contact_name or '',
                    'emergency_contact_phone': profile.emergency_contact_phone or '',
                    'emergency_contact_relationship': profile.emergency_contact_relationship or '',
                    
                    # ✅ Reporting Structure
                    'reports_to': profile.reports_to.get_full_name() if profile.reports_to else None,
                    'reports_to_id': str(profile.reports_to.id) if profile.reports_to else None,
                    
                    # ✅ Permissions
                    'can_approve_loans': profile.can_approve_loans,
                    'can_approve_accounts': profile.can_approve_accounts,
                    'max_approval_amount': float(profile.max_approval_amount) if profile.max_approval_amount else None,
                    
                    # ✅ ID Information
                    'id_type': getattr(profile, 'id_type', '') or '',
                    'id_number': getattr(profile, 'id_number', '') or '',
                    
                    # ✅ Images (ALL THREE)
                    'profile_picture': profile_pic_url,
                    'profile_picture_url': profile_pic_url,
                    'id_card_front': id_front_url,
                    'id_card_front_url': id_front_url,
                    'id_card_back': id_back_url,
                    'id_card_back_url': id_back_url,
                    
                    # ✅ CV Document
                    'cv_url': profile.get_cv_url(),
                    'cv_filename': profile.get_cv_filename(),
                    
                    # ✅ Metadata
                    'notes': profile.notes or '',
                    'created_at': profile.created_at,
                    'updated_at': profile.updated_at,
                }
            except StaffProfile.DoesNotExist:
                return None
        return None
class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing password
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate_old_password(self, value):
        """Verify old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, data):
        """Validate new passwords match"""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'New passwords do not match.'
            })
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ClientPasswordSetSerializer(serializers.Serializer):
    """
    Serializer for client first-time password setup
    """
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        """Validate passwords match and token is valid"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })
        
        # Validate token
        token = data['token']
        try:
            client_profile = ClientProfile.objects.get(password_reset_token=token)
            
            if not client_profile.is_token_valid(token):
                raise serializers.ValidationError({
                    'token': 'Token is invalid or has expired.'
                })
            
            data['client_profile'] = client_profile
            
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError({
                'token': 'Invalid token.'
            })
        
        return data
    
    def save(self):
        client_profile = self.validated_data['client_profile']
        user = client_profile.user
        
        # Set password
        user.set_password(self.validated_data['password'])
        user.save()
        
        # Mark password as set
        client_profile.has_set_password = True
        client_profile.password_reset_token = None
        client_profile.password_reset_expires = None
        client_profile.save()
        
        return user