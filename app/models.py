from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.crypto import get_random_string
from django.core.validators import RegexValidator
from cloudinary.models import CloudinaryField
import uuid
from decimal import Decimal
from datetime import timedelta

from django.core.validators import MinValueValidator, MaxValueValidator


class Branch(models.Model):
    """Branch/Office locations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Branches"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_approved', True)
        extra_fields.setdefault('user_role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User Model"""
    
    ROLE_CHOICES = [
        ('client', 'Client'),
        ('staff', 'Staff'),
        ('manager', 'Manager'),
        ('director', 'Director'),
        ('admin', 'Admin'),
    ]

    # Remove username, use email as unique identifier
    username = None
    email = models.EmailField(unique=True)
    
    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    
    # Branch (only for staff, manager, director)
    branch = models.ForeignKey(
        Branch, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    # Approval & Status
    is_approved = models.BooleanField(default=False, help_text="Admin must approve before user can login")
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Override groups and user_permissions to avoid clash
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    failed_login_attempts = models.IntegerField(
        default=0,
        help_text="Number of failed login attempts"
    )
    account_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Account locked until this datetime"
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'user_role']

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_role']),
            models.Index(fields=['is_approved', 'is_active']),
            models.Index(fields=['branch', 'user_role']),
            models.Index(fields=['failed_login_attempts']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.user_role})"

    def is_client(self):
        return self.user_role == 'client'

    def is_staff_member(self):
        return self.user_role == 'staff'

    def is_manager_role(self):
        return self.user_role == 'manager'

    def is_director_role(self):
        return self.user_role == 'director'

    def is_admin_role(self):
        return self.user_role == 'admin'

    def can_approve_users(self):
        """Only admin can approve users"""
        return self.user_role == 'admin'

    def can_manage_branch(self, branch):
        """Manager can manage their branch, Director/Admin can manage all"""
        if self.user_role in ['director', 'admin']:
            return True
        if self.user_role == 'manager' and self.branch == branch:
            return True
        return False

    def get_accessible_branches(self):
        """Get branches user can access"""
        if self.user_role in ['director', 'admin']:
            return Branch.objects.all()
        elif self.user_role in ['manager', 'staff']:
            return Branch.objects.filter(id=self.branch_id)
        return Branch.objects.none()

class ClientProfile(models.Model):
    """Extended profile for Clients"""
    
    # Client Level/Tier System
    LEVEL_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
        ('diamond', 'Diamond'),
    ]
    
    # Loan limits per level (in NGN)
    LEVEL_LIMITS = {
        'bronze': 50000,      # 50K
        'silver': 100000,     # 100K
        'gold': 500000,       # 500K
        'platinum': 1000000,  # 1M
        'diamond': 5000000,   # 5M
    }
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    
    # Client Level
    level = models.CharField(
        max_length=20, 
        choices=LEVEL_CHOICES, 
        default='bronze',
        help_text="Client tier determining loan limits"
    )
    
    # Password Setup
    has_set_password = models.BooleanField(
        default=False,
        help_text="Whether client has completed initial password setup"
    )
    password_reset_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_expires = models.DateTimeField(blank=True, null=True)
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], blank=True)
    
    # Address
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='Nigeria')
    
    # Identification
    id_type = models.CharField(max_length=50, choices=[
        ('national_id', 'National ID'),
        ('passport', 'International Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('voters_card', 'Voter\'s Card'),
    ], blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    
    # ID Card Images (Front & Back) - Using Cloudinary
    id_card_front = CloudinaryField(
        'id_card_front',
        folder='clients/id_cards/front',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Front side of ID card",
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    id_card_back = CloudinaryField(
        'id_card_back',
        folder='clients/id_cards/back',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Back side of ID card",
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # Employment/Financial
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Banking
    account_number = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bvn = models.CharField(max_length=11, blank=True, help_text="Bank Verification Number")
    
    # Credit & Risk
    credit_score = models.IntegerField(default=0)
    risk_rating = models.CharField(max_length=20, choices=[
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ], default='medium')
    
    # Relationship with institution
    assigned_staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_clients',
        limit_choices_to={'user_role': 'staff'}
    )
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='clients')
    
    # Profile Picture - Using Cloudinary
    profile_picture = CloudinaryField(
        'profile_picture',
        folder='clients/profile_pictures',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Client profile photo",
        transformation={
            'width': 400,
            'height': 400,
            'crop': 'fill',
            'gravity': 'face',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Internal notes about client")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['level']),
            models.Index(fields=['assigned_staff']),
            models.Index(fields=['branch']),
        ]

    def __str__(self):
        return f"Client Profile: {self.user.get_full_name()} - {self.get_level_display()}"

    def get_loan_limit(self):
        """Get maximum loan amount based on client level"""
        return self.LEVEL_LIMITS.get(self.level, 0)

    def can_borrow(self, amount):
        """Check if client can borrow specified amount based on level"""
        return amount <= self.get_loan_limit()

    def upgrade_level(self):
        """Upgrade client to next level"""
        levels = ['bronze', 'silver', 'gold', 'platinum', 'diamond']
        current_index = levels.index(self.level)
        if current_index < len(levels) - 1:
            self.level = levels[current_index + 1]
            self.save()
            return True
        return False

    def downgrade_level(self):
        """Downgrade client to previous level"""
        levels = ['bronze', 'silver', 'gold', 'platinum', 'diamond']
        current_index = levels.index(self.level)
        if current_index > 0:
            self.level = levels[current_index - 1]
            self.save()
            return True
        return False

    def generate_password_reset_token(self):
        """Generate secure token for password reset"""
        self.password_reset_token = get_random_string(64)
        self.password_reset_expires = timezone.now() + timedelta(hours=24)
        self.save()
        return self.password_reset_token

    def is_token_valid(self, token):
        """Check if password reset token is valid"""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        if self.password_reset_token != token:
            return False
        if timezone.now() > self.password_reset_expires:
            return False
        return True
    

class StaffProfile(models.Model):
    """Extended profile for Staff, Managers, Directors"""


    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')

    blood_group = models.CharField(
        max_length=5,
        choices=[
            ('A+', 'A+'),
            ('A-', 'A-'),
            ('B+', 'B+'),
            ('B-', 'B-'),
            ('AB+', 'AB+'),
            ('AB-', 'AB-'),
            ('O+', 'O+'),
            ('O-', 'O-'),
        ],
        blank=True,
        help_text="Blood group"
    )
    
    # Employment Information
    employee_id = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=100, help_text="Job title/position")
    department = models.CharField(max_length=50, choices=[
        ('operations', 'Operations'),
        ('loans', 'Loans'),
        ('savings', 'Savings'),
        ('customer_service', 'Customer Service'),
        ('accounts', 'Accounts'),
        ('IT', 'IT/Technical'),
        ('management', 'Management'),
        ('board', 'Board of Directors'),
    ])
    
    # Employment dates
    hire_date = models.DateField()
    termination_date = models.DateField(null=True, blank=True)
    
    # Compensation
    salary = models.DecimalField(max_digits=12, decimal_places=2)
    bank_account = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    
    # Personal
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], blank=True)
    address = models.TextField(blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=17, blank=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True)
    
    # Reports to (for hierarchy)
    reports_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        limit_choices_to={'user_role__in': ['manager', 'director', 'admin']}
    )
    
    # Permissions & Access
    can_approve_loans = models.BooleanField(default=False)
    can_approve_accounts = models.BooleanField(default=False)
    max_approval_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Maximum loan amount this user can approve"
    )
    
    # Documents - Using Cloudinary
    # Profile Picture
    profile_picture = CloudinaryField(
        'profile_picture',
        folder='staff/profile_pictures',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Staff profile photo",
        transformation={
            'width': 400,
            'height': 400,
            'crop': 'fill',
            'gravity': 'face',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # CV/Resume Document
    cv_document = CloudinaryField(
        'cv_document',
        folder='staff/cv_documents',
        null=True,
        blank=True,
        resource_type='raw',  # For PDF, DOC, DOCX files
        help_text="Current CV/Resume (PDF, DOC, DOCX)",
    )

    # ID Card Images (Front & Back) - Using Cloudinary
    id_card_front = CloudinaryField(
        'id_card_front',
        folder='staff/id_cards/front',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Front side of ID card",
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    id_card_back = CloudinaryField(
        'id_card_back',
        folder='staff/id_cards/back',
        null=True,
        blank=True,
        resource_type='image',
        help_text="Back side of ID card",
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # ID Information
    id_type = models.CharField(max_length=50, choices=[
        ('national_id', 'National ID'),
        ('passport', 'International Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('voters_card', 'Voter\'s Card'),
    ], blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Internal notes about staff member")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Staff Profiles"

    def __str__(self):
        return f"Staff Profile: {self.user.get_full_name()} - {self.designation}"

    def is_employment_active(self):
        return self.termination_date is None
    
    def get_cv_url(self):
        """Get the CV document URL"""
        if self.cv_document:
            return self.cv_document.url
        return None
    
    def get_cv_filename(self):
        """Extract filename from CV document"""
        if self.cv_document and hasattr(self.cv_document, 'public_id'):
            return self.cv_document.public_id.split('/')[-1]
        return None
    

# Savings and Loans
class SavingsAccount(models.Model):
    """Savings Account for Clients"""
    
    ACCOUNT_TYPE_CHOICES = [
        ('daily', 'Daily Savings'),
        ('weekly', 'Weekly Savings'),
        ('monthly', 'Monthly Savings'),
        ('fixed', 'Fixed Deposit'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_number = models.CharField(max_length=20, unique=True)
    client = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='savings_accounts',
        limit_choices_to={'user_role': 'client'}
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='savings_accounts')
    
    # Account details
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Balance (NO INTEREST)
    balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Current account balance"
    )
    
    # Minimum balance
    minimum_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Staff assignment
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_savings_accounts',
        limit_choices_to={'user_role__in': ['staff', 'manager', 'director', 'admin']}
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_savings_accounts',
        limit_choices_to={'user_role__in': ['manager', 'director', 'admin']}
    )
    
    # Dates
    date_opened = models.DateField(auto_now_add=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    date_closed = models.DateField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['branch']),
            models.Index(fields=['client', 'status', 'branch']),
        ]
    
    def __str__(self):
        return f"{self.account_number} - {self.client.get_full_name()} (₦{self.balance:,.2f})"
    
    def is_below_minimum(self):
        """Check if balance is below minimum"""
        return self.balance < self.minimum_balance
    
    def can_withdraw(self, amount):
        """Check if withdrawal is allowed"""
        if self.status != 'active':
            return False, "Account is not active"
        
        if (self.balance - amount) < self.minimum_balance:
            return False, f"Withdrawal would bring balance below minimum (₦{self.minimum_balance:,.2f})"
        
        return True, "Withdrawal allowed"



class Loan(models.Model):
    """
    Loan model with automatic interest calculation using flat rate method
    """
    
    # Status choices
    STATUS_CHOICES = [
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    ]
    
    REPAYMENT_FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    DISBURSEMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
    ]
    
    # Primary identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan_number = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Relationships
    client = models.ForeignKey('User', on_delete=models.PROTECT, related_name='loans')
    branch = models.ForeignKey('Branch', on_delete=models.PROTECT, related_name='loans')
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='loans_created')
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_approved')
    disbursed_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_disbursed')
    
    # Core loan details (what staff enters)
    principal_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))]
    )
    repayment_frequency = models.CharField(max_length=20, choices=REPAYMENT_FREQUENCY_CHOICES, default='monthly')
    duration_value = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of payment periods (days, weeks, or months depending on frequency)"
    )
    
    # Calculated fields (auto-populated)
    monthly_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=4,
        help_text="Monthly interest rate as decimal (e.g., 0.05 for 5%)",
        null=True,
        blank=True
    )
    annual_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Annual interest rate as percentage (e.g., 60 for 60%)",
        null=True,
        blank=True
    )
    duration_months = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Duration converted to months",
        null=True,
        blank=True
    )
    total_interest = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total interest to be paid"
    )
    total_repayment = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount to be repaid (principal + interest)"
    )
    installment_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount per installment"
    )
    number_of_installments = models.IntegerField(
        default=0,
        help_text="Total number of payments"
    )
    
    # Legacy fields for backward compatibility (same as total_repayment)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    loan_term = models.IntegerField(default=0, help_text="Duration in months (for display)")
    payment_frequency = models.CharField(max_length=20, default='monthly')
    
    # Loan purpose
    purpose = models.CharField(max_length=200)
    purpose_details = models.TextField(blank=True, null=True)
    
    # Collateral information
    collateral_type = models.CharField(max_length=100, blank=True, null=True)
    collateral_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    collateral_description = models.TextField(blank=True, null=True)
    
    # Guarantor information (First Guarantor)
    guarantor_name = models.CharField(max_length=200)
    guarantor_phone = models.CharField(max_length=20)
    guarantor_address = models.TextField()
    
    # Second Guarantor
    guarantor2_name = models.CharField(max_length=200)
    guarantor2_phone = models.CharField(max_length=20)
    guarantor2_address = models.TextField()
    
    # Payment tracking
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Status and workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')
    
    # Dates
    application_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    disbursement_date = models.DateTimeField(null=True, blank=True)
    first_repayment_date = models.DateField(null=True, blank=True)
    final_repayment_date = models.DateField(null=True, blank=True)
    next_repayment_date = models.DateField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    
    # Disbursement details
    disbursement_method = models.CharField(max_length=20, choices=DISBURSEMENT_METHOD_CHOICES, blank=True, null=True)
    bank_name = models.CharField(max_length=200, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_account_name = models.CharField(max_length=200, blank=True, null=True)
    disbursement_reference = models.CharField(max_length=100, blank=True, null=True)
    disbursement_notes = models.TextField(blank=True, null=True)
    amount_disbursed = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Approval/Rejection
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['loan_number']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['status', 'next_repayment_date']),
        ]
    
    def __str__(self):
        return f"{self.loan_number} - {self.client.get_full_name()}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate loan details automatically"""
        
        # Only calculate on creation or if core fields changed
        if not self.pk or self._state.adding:
            self.calculate_loan_details()
        
        # Update legacy fields for compatibility
        self.total_amount = self.total_repayment
        self.interest_rate = self.annual_interest_rate or Decimal('0.00')
        self.loan_term = int(self.duration_months or 0)
        self.payment_frequency = self.repayment_frequency
        
        # Set initial outstanding balance
        if not self.pk:
            self.outstanding_balance = self.total_repayment
        
        super().save(*args, **kwargs)
    
    def calculate_loan_details(self):
        """Calculate all loan details using LoanCalculator"""
        from .loan_calculator import LoanCalculator
        
        calc_result = LoanCalculator.calculate_loan(
            principal_amount=self.principal_amount,
            frequency=self.repayment_frequency,
            duration_value=self.duration_value,
            start_date=self.disbursement_date or timezone.now()
        )
        
        # Update calculated fields
        self.monthly_interest_rate = calc_result['monthly_interest_rate']
        self.annual_interest_rate = calc_result['annual_interest_rate']
        self.duration_months = calc_result['duration_months']
        self.total_interest = calc_result['total_interest']
        self.total_repayment = calc_result['total_repayment']
        self.installment_amount = calc_result['installment_amount']
        self.number_of_installments = calc_result['number_of_installments']
        self.first_repayment_date = calc_result['first_payment_date']
        self.final_repayment_date = calc_result['final_payment_date']
        self.next_repayment_date = calc_result['first_payment_date']
    
    def approve(self, approved_by):
        """Approve the loan"""
        if self.status != 'pending_approval':
            return False, f"Cannot approve loan with status: {self.get_status_display()}"
        
        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.save()
        return True, "Loan approved successfully"
    
    def reject(self, rejection_reason=''):
        """Reject the loan"""
        if self.status != 'pending_approval':
            return False, f"Cannot reject loan with status: {self.get_status_display()}"
        
        self.status = 'rejected'
        self.rejection_reason = rejection_reason
        self.save()
        return True, "Loan rejected"
    
    def disburse(self, disbursed_by):
        """Disburse the loan"""
        if self.status != 'approved':
            return False, f"Only approved loans can be disbursed. Current status: {self.get_status_display()}"
        
        self.status = 'active'
        self.disbursed_by = disbursed_by
        self.disbursement_date = timezone.now()
        self.amount_disbursed = self.principal_amount
        
        # Recalculate payment dates based on actual disbursement date
        self.calculate_loan_details()
        
        # ✅ FIX: Explicitly set outstanding_balance after calculation
        self.outstanding_balance = self.total_repayment
        
        self.save()
        return True, "Loan disbursed successfully"
    
    # def disburse(self, disbursed_by):
    #     """Disburse the loan"""
    #     if self.status != 'approved':
    #         return False, f"Only approved loans can be disbursed. Current status: {self.get_status_display()}"
        
    #     self.status = 'active'
    #     self.disbursed_by = disbursed_by
    #     self.disbursement_date = timezone.now()
    #     self.amount_disbursed = self.principal_amount
        
    #     # Recalculate payment dates based on actual disbursement date
    #     self.calculate_loan_details()
        
    #     self.save()
    #     return True, "Loan disbursed successfully"
    
    def record_repayment(self, amount):
        """Record a loan repayment"""
        if self.status not in ['active', 'overdue']:
            raise ValueError(f"Cannot record repayment for loan with status: {self.get_status_display()}")
        
        if amount <= 0:
            raise ValueError("Repayment amount must be greater than zero")
        
        if amount > self.outstanding_balance:
            raise ValueError(f"Repayment amount (₦{amount:,.2f}) exceeds outstanding balance (₦{self.outstanding_balance:,.2f})")
        
        # Update payment tracking
        self.amount_paid += amount
        self.outstanding_balance -= amount
        
        # Update next payment date
        from .loan_calculator import LoanCalculator
        self.next_repayment_date = LoanCalculator.calculate_next_payment_date(
            self.next_repayment_date or timezone.now().date(),
            self.repayment_frequency
        )
        
        # Check if loan is fully paid
        if self.outstanding_balance <= Decimal('0.01'):  # Account for rounding
            self.outstanding_balance = Decimal('0.00')
            self.status = 'completed'
            self.completion_date = timezone.now()
        else:
            # Check if overdue
            if self.next_repayment_date and self.next_repayment_date < timezone.now().date():
                self.status = 'overdue'
            else:
                self.status = 'active'
        
        self.save()
        return self.outstanding_balance
    
    @property
    def balance(self):
        """Alias for outstanding_balance"""
        return self.outstanding_balance
    
    @property
    def client_name(self):
        """Get client full name"""
        return self.client.get_full_name() if self.client else ""
    
    @property
    def client_email(self):
        """Get client email"""
        return self.client.email if self.client else ""
    
    @property
    def client_phone(self):
        """Get client phone"""
        return self.client.phone if self.client else ""
    
    @property
    def client_id(self):
        """Get client ID as string"""
        return str(self.client.id) if self.client else ""
    
    @property
    def branch_name(self):
        """Get branch name"""
        return self.branch.name if self.branch else ""
    
    @property
    def created_by_name(self):
        """Get name of staff who created the loan"""
        return self.created_by.get_full_name() if self.created_by else ""
    
    @property
    def approved_by_name(self):
        """Get name of staff who approved the loan"""
        return self.approved_by.get_full_name() if self.approved_by else ""
    
    @property
    def disbursed_by_name(self):
        """Get name of staff who disbursed the loan"""
        return self.disbursed_by.get_full_name() if self.disbursed_by else ""
    
    @property
    def days_overdue(self):
        """Calculate days overdue if applicable"""
        if self.status == 'overdue' and self.next_repayment_date:
            delta = timezone.now().date() - self.next_repayment_date
            return delta.days if delta.days > 0 else 0
        return 0
    
    def get_rate_display(self):
        """Get formatted rate display"""
        if self.monthly_interest_rate:
            monthly_pct = float(self.monthly_interest_rate * 100)
            return f"{monthly_pct:.2f}%/month"
        return "N/A"
    
    def get_payment_frequency_display_detailed(self):
        """Get detailed payment frequency display"""
        freq_map = {
            'daily': 'Daily',
            'weekly': 'Weekly',
            'biweekly': 'Bi-Weekly (Every 2 weeks)',
            'monthly': 'Monthly',
        }
        return freq_map.get(self.repayment_frequency, self.repayment_frequency)

# class Loan(models.Model):
#     """
#     Loan Model with Flat Rate Interest Calculation
#     Uses tiered pricing based on frequency and duration
#     """
    
#     STATUS_CHOICES = [
#         ('pending', 'Pending Approval'),
#         ('approved', 'Approved - Awaiting Disbursement'),
#         ('active', 'Active - Repayment Ongoing'),
#         ('overdue', 'Overdue'),
#         ('completed', 'Fully Repaid'),
#         ('rejected', 'Rejected'),
#         ('written_off', 'Written Off'),
#     ]
    
#     REPAYMENT_FREQUENCY_CHOICES = [
#         ('daily', 'Daily'),
#         ('weekly', 'Weekly'),
#         ('biweekly', 'Bi-Weekly'),
#         ('monthly', 'Monthly'),
#     ]
    
#     # Primary fields
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     loan_number = models.CharField(max_length=20, unique=True)
#     client = models.ForeignKey(
#         'User',
#         on_delete=models.PROTECT,
#         related_name='loans',
#         limit_choices_to={'user_role': 'client'}
#     )
#     branch = models.ForeignKey('Branch', on_delete=models.PROTECT, related_name='loans')
    
#     # Loan details
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     principal_amount = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         help_text="Original loan amount"
#     )
    
#     # NEW: Duration and frequency instead of duration_months
#     repayment_frequency = models.CharField(
#         max_length=20,
#         choices=REPAYMENT_FREQUENCY_CHOICES,
#         default='monthly',
#         help_text="How often the client will make payments"
#     )
#     duration_value = models.IntegerField(
#         help_text="Number of payment periods (e.g., 30 days, 12 weeks, 6 months)"
#     )
    
#     # NEW: Store the monthly rate used for calculation
#     monthly_interest_rate = models.DecimalField(
#         max_digits=5,
#         decimal_places=4,
#         help_text="Monthly interest rate used (as decimal, e.g., 0.0500 for 5%)"
#     )
    
#     # NEW: Store annual rate for display
#     annual_interest_rate = models.DecimalField(
#         max_digits=6,
#         decimal_places=2,
#         help_text="Annual interest rate percentage for display"
#     )
    
#     # Calculated amounts (auto-calculated using flat rate)
#     total_interest = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         help_text="Total interest to be paid (P × r × t)"
#     )
#     total_repayment = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         help_text="Principal + Total Interest"
#     )
#     installment_amount = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         help_text="Amount to pay per installment"
#     )
#     number_of_installments = models.IntegerField(
#         help_text="Total number of payments",
#         default=0
#     )
    
#     # Current balances
#     amount_disbursed = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Actual amount disbursed to client"
#     )
#     amount_paid = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Total amount paid so far"
#     )
#     outstanding_balance = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         help_text="Remaining amount to be paid"
#     )
    
#     # Loan purpose
#     purpose = models.CharField(max_length=200, help_text="Reason for loan")
#     purpose_details = models.TextField(blank=True)
    
#     # Collateral/Guarantor
#     collateral_type = models.CharField(max_length=100, blank=True)
#     collateral_value = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         null=True,
#         blank=True
#     )
#     collateral_description = models.TextField(blank=True)
    
#     guarantor_name = models.CharField(max_length=200, blank=True)
#     guarantor_phone = models.CharField(max_length=17, blank=True)
#     guarantor_address = models.TextField(blank=True)
    
#     # NEW: Second guarantor support
#     guarantor2_name = models.CharField(max_length=200, blank=True)
#     guarantor2_phone = models.CharField(max_length=17, blank=True)
#     guarantor2_address = models.TextField(blank=True)
    
#     # Staff assignment
#     created_by = models.ForeignKey(
#         'User',
#         on_delete=models.SET_NULL,
#         null=True,
#         related_name='created_loans',
#         limit_choices_to={'user_role__in': ['staff', 'manager', 'director', 'admin']}
#     )
#     approved_by = models.ForeignKey(
#         'User',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='approved_loans',
#         limit_choices_to={'user_role__in': ['manager', 'director', 'admin']}
#     )
#     disbursed_by = models.ForeignKey(
#         'User',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='disbursed_loans',
#         limit_choices_to={'user_role__in': ['staff', 'manager', 'director', 'admin']}
#     )
    
#     # Important dates
#     application_date = models.DateField(auto_now_add=True)
#     approval_date = models.DateTimeField(null=True, blank=True)
#     disbursement_date = models.DateField(null=True, blank=True)
#     first_repayment_date = models.DateField(null=True, blank=True)
#     next_repayment_date = models.DateField(null=True, blank=True)
#     final_repayment_date = models.DateField(null=True, blank=True)
#     completion_date = models.DateField(null=True, blank=True)
    
#     # Disbursement details
#     disbursement_method = models.CharField(
#         max_length=20,
#         choices=[
#             ('bank_transfer', 'Bank Transfer'),
#             ('cash', 'Cash'),
#             ('mobile_money', 'Mobile Money'),
#             ('cheque', 'Cheque')
#         ],
#         blank=True
#     )
#     bank_name = models.CharField(max_length=100, blank=True)
#     bank_account_number = models.CharField(max_length=20, blank=True)
#     bank_account_name = models.CharField(max_length=200, blank=True)
#     disbursement_reference = models.CharField(max_length=100, blank=True)
#     disbursement_notes = models.TextField(blank=True)
    
#     # Deductions (processing fees, etc.)
#     deduction_amount = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Amount deducted from disbursement (fees, insurance, etc.)"
#     )
#     deduction_reason = models.CharField(max_length=200, blank=True)
#     net_disbursement = models.DecimalField(
#         max_digits=15,
#         decimal_places=2,
#         default=Decimal('0.00'),
#         help_text="Actual amount received by client (principal - deductions)"
#     )
    
#     # Overdue tracking
#     days_overdue = models.IntegerField(default=0)
#     last_overdue_check = models.DateField(null=True, blank=True)
    
#     # Rejection reason
#     rejection_reason = models.TextField(blank=True)
    
#     # Metadata
#     notes = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['loan_number']),
#             models.Index(fields=['client', 'status']),
#             models.Index(fields=['status']),
#             models.Index(fields=['branch']),
#             models.Index(fields=['next_repayment_date']),
#             models.Index(fields=['disbursement_date']),
#             models.Index(fields=['repayment_frequency']),
#         ]
    
#     def __str__(self):
#         return f"{self.loan_number} - {self.client.get_full_name()} (₦{self.outstanding_balance:,.2f})"
    
#     def save(self, *args, **kwargs):
#         """
#         Auto-calculate loan details on save if not already calculated.
#         Uses the LoanCalculator utility for accurate flat rate calculation.
#         """
#         # Only calculate if this is a new loan or if amounts aren't set
#         if not self.total_interest or not self.total_repayment:
#             from .loan_calculator import LoanCalculator
            
#             # Calculate loan details
#             calc_result = LoanCalculator.calculate_loan(
#                 principal_amount=self.principal_amount,
#                 frequency=self.repayment_frequency,
#                 duration_value=self.duration_value
#             )
            
#             # Set calculated fields
#             self.monthly_interest_rate = calc_result['monthly_interest_rate']
#             self.annual_interest_rate = calc_result['annual_interest_rate']
#             self.total_interest = calc_result['total_interest']
#             self.total_repayment = calc_result['total_repayment']
#             self.installment_amount = calc_result['installment_amount']
#             self.number_of_installments = calc_result['number_of_installments']
#             self.outstanding_balance = calc_result['outstanding_balance']
        
#         super().save(*args, **kwargs)
    
#     def get_rate_display(self):
#         """Get formatted interest rate for display."""
#         return f"{float(self.monthly_interest_rate * 100):.2f}% per month ({float(self.annual_interest_rate):.1f}% annual)"
    
#     def get_payment_frequency_display_detailed(self):
#         """Get detailed frequency description."""
#         freq_map = {
#             'daily': f'{self.duration_value} days',
#             'weekly': f'{self.duration_value} weeks',
#             'biweekly': f'{self.duration_value} bi-weekly periods',
#             'monthly': f'{self.duration_value} months',
#         }
#         return freq_map.get(self.repayment_frequency, self.repayment_frequency)






class Transaction(models.Model):
    """All financial transactions (deposits, withdrawals, loan repayments, disbursements)"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('deposit', 'Savings Deposit'),
        ('withdrawal', 'Savings Withdrawal'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('fee', 'Fee/Charge'),
        ('reversal', 'Reversal'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_ref = models.CharField(max_length=50, unique=True)
    
    # Transaction details
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Related accounts
    client = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='transactions',
        limit_choices_to={'user_role': 'client'}
    )
    savings_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transactions'
    )
    loan = models.ForeignKey(
        Loan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transactions'
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='transactions')
    
    # Balance tracking (for savings)
    balance_before = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Staff who processed/requested
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_transactions',
        limit_choices_to={'user_role__in': ['staff', 'manager', 'director', 'admin']}
    )
    
    # Approval workflow fields
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transactions',
        limit_choices_to={'user_role__in': ['manager', 'director', 'admin']}
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Transaction metadata
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    transaction_date = models.DateTimeField(auto_now_add=True)
    
    # Reversal tracking
    reversed_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversals'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['transaction_ref']),
            models.Index(fields=['client', 'transaction_type']),
            models.Index(fields=['savings_account']),
            models.Index(fields=['loan']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['branch', 'transaction_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.transaction_ref} - {self.get_transaction_type_display()} (₦{self.amount:,.2f})"

class Notification(models.Model):
    """Notifications for users about system events"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('client_registered', 'New Client Registered'),
        ('client_approved', 'Client Approved'),
        ('client_rejected', 'Client Rejected'),
        ('loan_applied', 'Loan Application Submitted'),
        ('loan_approved', 'Loan Approved'),
        ('loan_rejected', 'Loan Rejected'),
        ('loan_disbursed', 'Loan Disbursed'),
        ('loan_overdue', 'Loan Overdue'),
        ('loan_completed', 'Loan Completed'),
        ('savings_created', 'Savings Account Created'),
        ('savings_approved', 'Savings Account Approved'),
        ('deposit_made', 'Deposit Made'),
        ('withdrawal_made', 'Withdrawal Made'),
        ('staff_created', 'Staff Account Created'),
        ('staff_deactivated', 'Staff Deactivated'),
        ('assignment_changed', 'Assignment Changed'),
        ('system_alert', 'System Alert'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipient
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    # Notification details
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects (optional)
    related_client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='related_notifications',
        limit_choices_to={'user_role': 'client'}
    )
    related_loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    related_savings = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Priority
    is_urgent = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()



# Guarantor and Next of Kin Models (Professional Implementation)
# Replace the placeholder models at the bottom of models.py with these

class Guarantor(models.Model):
    """Guarantor information for clients - supports multiple guarantors per client"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='guarantors',
        limit_choices_to={'user_role': 'client'}
    )
    
    # Guarantor details
    name = models.CharField(max_length=255)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17)
    email = models.EmailField(blank=True, help_text="Optional guarantor email")
    relationship = models.CharField(max_length=100, help_text="Relationship to client (e.g., Brother, Friend)")
    address = models.TextField()
    
    # Guarantor employment info (optional)
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    
    # Guarantor financial info (optional)
    monthly_income = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Guarantor's monthly income"
    )
    
    # Guarantor ID (optional)
    id_type = models.CharField(max_length=50, choices=[
        ('national_id', 'National ID'),
        ('passport', 'International Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('voters_card', 'Voter\'s Card'),
    ], blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Additional notes about guarantor")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['phone']),
        ]
        verbose_name = "Guarantor"
        verbose_name_plural = "Guarantors"
    
    def __str__(self):
        return f"Guarantor: {self.name} for {self.client.get_full_name()}"


class NextOfKin(models.Model):
    """Next of Kin information for clients - one per client"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='next_of_kin',
        limit_choices_to={'user_role': 'client'}
    )
    
    # Next of Kin details
    name = models.CharField(max_length=255)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17)
    email = models.EmailField(blank=True, help_text="Optional NOK email")
    relationship = models.CharField(max_length=100, help_text="Relationship to client (e.g., Mother, Spouse)")
    address = models.TextField()
    
    # Additional info (optional)
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Additional notes about next of kin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['phone']),
        ]
        verbose_name = "Next of Kin"
        verbose_name_plural = "Next of Kin"
    
    def __str__(self):
        return f"NOK: {self.name} for {self.client.get_full_name()}"






