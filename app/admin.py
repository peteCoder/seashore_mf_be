from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    User,
    Branch,
    ClientProfile,
    StaffProfile,
    SavingsAccount,
    Loan,
    Transaction,
    Notification,
    NextOfKin,
    Guarantor,

)


admin.site.register(NextOfKin)
admin.site.register(Guarantor)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'state', 'phone', 'email', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'city']
    search_fields = ['name', 'code', 'city', 'state', 'email', 'phone']
    ordering = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('address', 'city', 'state', 'phone', 'email')
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class ClientProfileInline(admin.StackedInline):
    model = ClientProfile
    can_delete = False
    verbose_name_plural = 'Client Profile'
    fk_name = 'user'
    
    fieldsets = (
        ('Client Level & Status', {
            'fields': ('level', 'has_set_password')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'profile_picture')
        }),
        ('Address Information', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Identification', {
            'fields': ('id_type', 'id_number', 'id_card_front', 'id_card_back')
        }),
        ('Employment & Financial', {
            'fields': ('occupation', 'employer', 'monthly_income')
        }),
        ('Banking Information', {
            'fields': ('account_number', 'bank_name', 'bvn')
        }),
        ('Credit & Risk Assessment', {
            'fields': ('credit_score', 'risk_rating')
        }),
        ('Relationship Management', {
            'fields': ('assigned_staff', 'branch', 'notes')
        }),
    )
    
    readonly_fields = []


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'
    fk_name = 'user'
    
    fieldsets = (
        ('Employment Information', {
            'fields': ('employee_id', 'designation', 'department', 'hire_date', 'termination_date')
        }),
        ('Compensation', {
            'fields': ('salary', 'bank_account', 'bank_name')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'address', 'profile_picture')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship')
        }),
        ('Reporting Structure', {
            'fields': ('reports_to',)
        }),
        ('Permissions & Approval Limits', {
            'fields': ('can_approve_loans', 'can_approve_accounts', 'max_approval_amount')
        }),
        ('Documents', {
            'fields': ('cv_document',)
        }),
        ('Additional Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'email', 'full_name_display', 'user_role', 'branch',
        'approval_status', 'active_status', 'created_at'
    ]
    list_filter = ['user_role', 'is_approved', 'is_active', 'branch', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Role & Branch', {'fields': ('user_role', 'branch')}),
        ('Permissions', {
            'fields': ('is_active', 'is_approved', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 
                      'user_role', 'branch', 'is_approved'),
        }),
    )
    
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        
        inlines = []
        if obj.user_role == 'client':
            inlines.append(ClientProfileInline(self.model, self.admin_site))
        elif obj.user_role in ['staff', 'manager', 'director', 'admin']:
            inlines.append(StaffProfileInline(self.model, self.admin_site))
        
        return inlines
    
    def full_name_display(self, obj):
        return obj.get_full_name()
    full_name_display.short_description = 'Full Name'
    
    def approval_status(self, obj):
        if obj.is_approved:
            return format_html('<span style="color: green; font-weight: bold;">✓ Approved</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
    approval_status.short_description = 'Approval'
    
    def active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    active_status.short_description = 'Status'
    
    actions = ['approve_users', 'deactivate_users', 'activate_users']
    
    def approve_users(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} user(s) approved successfully.')
    approve_users.short_description = 'Approve selected users'
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated successfully.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) activated successfully.')
    activate_users.short_description = 'Activate selected users'


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'level_badge', 'branch', 'assigned_staff', 
        'credit_score', 'risk_badge', 'loan_limit_display', 'has_set_password'
    ]
    list_filter = ['level', 'risk_rating', 'branch', 'gender', 'has_set_password', 'id_type']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name', 
        'id_number', 'bvn', 'phone'
    ]
    raw_id_fields = ['user', 'assigned_staff']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 
        'profile_picture_preview', 'id_card_front_preview', 'id_card_back_preview',
        'loan_limit_readonly',  # Changed from loan_limit_display
        'password_reset_token', 'password_reset_expires'
    ]
    
    fieldsets = (
        ('User & Level', {
            'fields': ('user', 'level', 'has_set_password')
        }),
        ('Profile Picture', {
            'fields': ('profile_picture', 'profile_picture_preview')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Identification', {
            'fields': (
                'id_type', 'id_number',
                'id_card_front', 'id_card_front_preview',
                'id_card_back', 'id_card_back_preview'
            )
        }),
        ('Employment & Financial', {
            'fields': ('occupation', 'employer', 'monthly_income')
        }),
        ('Banking', {
            'fields': ('account_number', 'bank_name', 'bvn')
        }),
        ('Credit & Risk', {
            'fields': ('credit_score', 'risk_rating', 'loan_limit_readonly')  # Changed here
        }),
        ('Relationship', {
            'fields': ('assigned_staff', 'branch', 'notes')
        }),
        ('Password Reset (Read-only)', {
            'fields': ('password_reset_token', 'password_reset_expires'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['upgrade_client_level', 'downgrade_client_level', 'reset_to_bronze']
    
    def user_link(self, obj):
        url = reverse('admin:app_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
    user_link.short_description = 'Client Name'
    
    def level_badge(self, obj):
        colors = {
            'bronze': '#CD7F32',
            'silver': '#C0C0C0',
            'gold': '#FFD700',
            'platinum': '#E5E4E2',
            'diamond': '#B9F2FF'
        }
        color = colors.get(obj.level, '#gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; text-transform: uppercase;">{}</span>',
            color, obj.get_level_display()
        )
    level_badge.short_description = 'Level'
    
    def risk_badge(self, obj):
        colors = {
            'low': 'green',
            'medium': 'orange',
            'high': 'red'
        }
        color = colors.get(obj.risk_rating, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_risk_rating_display()
        )
    risk_badge.short_description = 'Risk'
    
    def loan_limit_display(self, obj):
        """For list_display - formats the loan limit"""
        from decimal import Decimal
        limit = obj.get_loan_limit()
        # Ensure we have a numeric value
        try:
            limit_value = Decimal(str(limit)) if limit is not None else Decimal('0')
            return format_html('₦{:,.2f}', limit_value)
        except (ValueError, TypeError):
            return '₦0.00'
    loan_limit_display.short_description = 'Loan Limit'
    
    def loan_limit_readonly(self, obj):
        """For readonly_fields - displays the loan limit in detail view"""
        from decimal import Decimal
        if obj and obj.pk:
            limit = obj.get_loan_limit()
            try:
                limit_value = Decimal(str(limit)) if limit is not None else Decimal('0')
                return format_html('₦{:,.2f}', limit_value)
            except (ValueError, TypeError):
                return '₦0.00'
        return '₦0.00'
    loan_limit_readonly.short_description = 'Loan Limit'
    
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return mark_safe(f'<img src="{obj.profile_picture.url}" width="150" height="150" style="border-radius: 50%;" />')
        return "No image"
    profile_picture_preview.short_description = 'Profile Picture Preview'
    
    def id_card_front_preview(self, obj):
        if obj.id_card_front:
            return mark_safe(f'<img src="{obj.id_card_front.url}" width="300" style="border: 1px solid #ddd; border-radius: 4px;" />')
        return "No image"
    id_card_front_preview.short_description = 'ID Card Front Preview'
    
    def id_card_back_preview(self, obj):
        if obj.id_card_back:
            return mark_safe(f'<img src="{obj.id_card_back.url}" width="300" style="border: 1px solid #ddd; border-radius: 4px;" />')
        return "No image"
    id_card_back_preview.short_description = 'ID Card Back Preview'
    
    def upgrade_client_level(self, request, queryset):
        upgraded = 0
        for client in queryset:
            if client.upgrade_level():
                upgraded += 1
        self.message_user(request, f'{upgraded} client(s) upgraded successfully.')
    upgrade_client_level.short_description = 'Upgrade client level'
    
    def downgrade_client_level(self, request, queryset):
        downgraded = 0
        for client in queryset:
            if client.downgrade_level():
                downgraded += 1
        self.message_user(request, f'{downgraded} client(s) downgraded successfully.')
    downgrade_client_level.short_description = 'Downgrade client level'
    
    def reset_to_bronze(self, request, queryset):
        updated = queryset.update(level='bronze')
        self.message_user(request, f'{updated} client(s) reset to Bronze level.')
    reset_to_bronze.short_description = 'Reset to Bronze level'

    
@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'employee_id', 'designation', 'department', 
        'hire_date', 'employment_status', 'can_approve_display'
    ]
    list_filter = [
        'department', 'can_approve_loans', 'can_approve_accounts', 
        'hire_date', 'gender'
    ]
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name', 
        'employee_id', 'designation'
    ]
    raw_id_fields = ['user', 'reports_to']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 
        'profile_picture_preview', 'cv_document_link', 'employment_status'
    ]
    
    fieldsets = (
        ('User & Employment', {
            'fields': ('user', 'employee_id', 'designation', 'department')
        }),
        ('Profile Picture', {
            'fields': ('profile_picture', 'profile_picture_preview')
        }),
        ('Employment Dates', {
            'fields': ('hire_date', 'termination_date', 'employment_status')
        }),
        ('Compensation', {
            'fields': ('salary', 'bank_account', 'bank_name')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'address')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship')
        }),
        ('Reporting Structure', {
            'fields': ('reports_to',)
        }),
        ('Permissions & Approval Limits', {
            'fields': ('can_approve_loans', 'can_approve_accounts', 'max_approval_amount')
        }),
        ('Documents', {
            'fields': ('cv_document', 'cv_document_link')
        }),
        ('Additional Notes', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:app_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
    user_link.short_description = 'Staff Name'
    
    def employment_status(self, obj):
        if obj.is_employment_active():
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Terminated ({})</span>',
            obj.termination_date.strftime('%Y-%m-%d') if obj.termination_date else 'N/A'
        )
    employment_status.short_description = 'Employment Status'
    
    def can_approve_display(self, obj):
        approvals = []
        if obj.can_approve_loans:
            approvals.append('Loans')
        if obj.can_approve_accounts:
            approvals.append('Accounts')
        
        if approvals:
            return format_html('<span style="color: green;">✓ {}</span>', ', '.join(approvals))
        return format_html('<span style="color: gray;">No approvals</span>')
    can_approve_display.short_description = 'Can Approve'
    
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return mark_safe(f'<img src="{obj.profile_picture.url}" width="150" height="150" style="border-radius: 50%;" />')
        return "No image"
    profile_picture_preview.short_description = 'Profile Picture Preview'
    
    def cv_document_link(self, obj):
        if obj.cv_document:
            filename = obj.get_cv_filename() or 'CV Document'
            return format_html(
                '<a href="{}" target="_blank" style="color: blue;">📄 {}</a>',
                obj.get_cv_url(), filename
            )
        return "No CV uploaded"
    cv_document_link.short_description = 'CV Document'


# ============================================
# LOANS, SAVINGS, NOTIFICATION AND TRANSACTIONS
# ============================================


@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = [
        'account_number', 'client_link', 'account_type', 'status_badge',
        'balance_display', 'branch', 'date_opened'
    ]
    list_filter = ['status', 'account_type', 'branch', 'date_opened']
    search_fields = [
        'account_number', 'client__email', 'client__first_name', 'client__last_name'
    ]
    raw_id_fields = ['client', 'branch', 'created_by', 'approved_by']
    readonly_fields = [
        'id', 'account_number', 'balance',
        'date_opened', 'date_approved',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_number', 'client', 'branch', 'account_type', 'status')
        }),
        ('Balance', {
            'fields': ('balance', 'minimum_balance')
        }),
        ('Staff & Approval', {
            'fields': ('created_by', 'approved_by', 'date_approved')
        }),
        ('Dates', {
            'fields': ('date_opened', 'date_closed')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_accounts']
    
    def client_link(self, obj):
        url = reverse('admin:app_user_change', args=[obj.client.id])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
    client_link.short_description = 'Client'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'active': 'green',
            'suspended': 'red',
            'closed': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


    def balance_display(self, obj):
        # Ensure balance is converted to a Decimal or float
        from decimal import Decimal
        try:
            # Convert balance to Decimal to handle any type issues
            balance = Decimal(str(obj.balance))
            return format_html('₦{:,.2f}', balance)
        except (ValueError, TypeError, AttributeError):
            # Fallback if balance is None or invalid
            return format_html('₦0.00')
    balance_display.short_description = 'Balance'
    
    # def balance_display(self, obj):
    #     return format_html('₦{:,.2f}', obj.balance)
    # balance_display.short_description = 'Balance'
    
    def approve_accounts(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='active')
        self.message_user(request, f'{updated} account(s) approved successfully.')
    approve_accounts.short_description = 'Approve selected accounts'


# @admin.register(Loan)
# class LoanAdmin(admin.ModelAdmin):
#     list_display = [
#         'loan_number', 'client_link', 'principal_display', 'outstanding_display',
#         'status_badge', 'next_repayment_date', 'days_overdue_display', 'branch'
#     ]
#     list_filter = [
#         'status', 'repayment_frequency', 'branch', 'application_date',
#         'disbursement_date', 'days_overdue'
#     ]
#     search_fields = [
#         'loan_number', 'client__email', 'client__first_name',
#         'client__last_name', 'purpose'
#     ]
#     raw_id_fields = ['client', 'branch', 'created_by', 'approved_by', 'disbursed_by']
#     readonly_fields = [
#         'id', 'loan_number', 'total_interest', 'total_repayment',
#         'amount_disbursed', 'amount_paid', 'outstanding_balance',
#         'application_date', 'approval_date', 'disbursement_date',
#         'completion_date', 'days_overdue', 'last_overdue_check',
#         'created_at', 'updated_at'
#     ]
    
#     fieldsets = (
#         ('Loan Information', {
#             'fields': ('loan_number', 'client', 'branch', 'status')
#         }),
#         ('Loan Terms', {
#             'fields': (
#                 'principal_amount', 'interest_rate', 'duration_months',
#                 'repayment_frequency', 'installment_amount'
#             )
#         }),
#         ('Calculated Amounts', {
#             'fields': ('total_interest', 'total_repayment')
#         }),
#         ('Current Status', {
#             'fields': ('amount_disbursed', 'amount_paid', 'outstanding_balance')
#         }),
#         ('Purpose & Collateral', {
#             'fields': (
#                 'purpose', 'purpose_details', 'collateral_type',
#                 'collateral_value', 'guarantor_name', 'guarantor_phone',
#                 'guarantor_address'
#             )
#         }),
#         ('Supporting Documents', {
#             'fields': ('supporting_document_1', 'supporting_document_2')
#         }),
#         ('Staff & Approval', {
#             'fields': ('created_by', 'approved_by', 'disbursed_by')
#         }),
#         ('Important Dates', {
#             'fields': (
#                 'application_date', 'approval_date', 'disbursement_date',
#                 'first_repayment_date', 'next_repayment_date',
#                 'final_repayment_date', 'completion_date'
#             )
#         }),
#         ('Overdue Tracking', {
#             'fields': ('days_overdue', 'last_overdue_check')
#         }),
#         ('Rejection', {
#             'fields': ('rejection_reason',),
#             'classes': ('collapse',)
#         }),
#         ('Notes', {
#             'fields': ('notes',)
#         }),
#         ('System Information', {
#             'fields': ('id', 'created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     actions = ['approve_loans', 'check_overdue']
    
#     def client_link(self, obj):
#         url = reverse('admin:app_user_change', args=[obj.client.id])
#         return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
#     client_link.short_description = 'Client'
    
#     def status_badge(self, obj):
#         colors = {
#             'pending': 'orange',
#             'approved': 'blue',
#             'active': 'green',
#             'overdue': 'red',
#             'completed': 'gray',
#             'rejected': 'darkred',
#         }
#         color = colors.get(obj.status, 'gray')
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{}</span>',
#             color, obj.get_status_display()
#         )
#     status_badge.short_description = 'Status'
    
#     def principal_display(self, obj):
#         return format_html('₦{:,.2f}', obj.principal_amount)
#     principal_display.short_description = 'Principal'
    
#     def outstanding_display(self, obj):
#         return format_html('₦{:,.2f}', obj.outstanding_balance)
#     outstanding_display.short_description = 'Outstanding'
    
#     def days_overdue_display(self, obj):
#         if obj.days_overdue > 0:
#             return format_html(
#                 '<span style="color: red; font-weight: bold;">{} days</span>',
#                 obj.days_overdue
#             )
#         return '—'
#     days_overdue_display.short_description = 'Days Overdue'
    
#     def approve_loans(self, request, queryset):
#         updated = queryset.filter(status='pending').update(status='approved')
#         self.message_user(request, f'{updated} loan(s) approved successfully.')
#     approve_loans.short_description = 'Approve selected loans'
    
#     def check_overdue(self, request, queryset):
#         count = 0
#         for loan in queryset.filter(status='active'):
#             if loan.check_overdue():
#                 count += 1
#         self.message_user(request, f'{count} loan(s) marked as overdue.')
#     check_overdue.short_description = 'Check for overdue loans'



class LoanAdmin(admin.ModelAdmin):
    """Admin interface for Loan model"""
    
    # List display
    list_display = [
        'loan_number',
        'client_name_link',
        'principal_amount_formatted',
        'outstanding_balance_formatted',
        'status_colored',
        'repayment_frequency',
        'application_date',
        'days_overdue_display',
    ]
    
    # List filters
    list_filter = [
        'status',
        'repayment_frequency',
        'disbursement_method',
        'branch',
        'application_date',
        'disbursement_date',
    ]
    
    # Search fields
    search_fields = [
        'loan_number',
        'client__first_name',
        'client__last_name',
        'client__email',
        'purpose',
    ]
    
    # Read-only fields
    readonly_fields = [
        'id',
        'loan_number',
        'monthly_interest_rate',
        'annual_interest_rate',
        'duration_months',
        'total_interest',
        'total_repayment',
        'installment_amount',
        'number_of_installments',
        'outstanding_balance',
        'amount_paid',
        'application_date',
        'approval_date',
        'disbursement_date',
        'created_at',
        'updated_at',
        'days_overdue_display',
        'payment_progress_bar',
    ]
    
    # Fieldsets for organized display
    fieldsets = (
        ('Identification', {
            'fields': (
                'id',
                'loan_number',
                'status',
            )
        }),
        ('Client & Branch', {
            'fields': (
                'client',
                'branch',
                'created_by',
                'approved_by',
                'disbursed_by',
            )
        }),
        ('Loan Details (Input)', {
            'fields': (
                'principal_amount',
                'repayment_frequency',
                'duration_value',
            ),
            'description': 'These are the core fields entered by staff. Other amounts are auto-calculated.'
        }),
        ('Calculated Amounts (Auto-generated)', {
            'fields': (
                'monthly_interest_rate',
                'annual_interest_rate',
                'duration_months',
                'total_interest',
                'total_repayment',
                'installment_amount',
                'number_of_installments',
            ),
            'classes': ('collapse',),
            'description': 'These fields are automatically calculated based on the loan details.'
        }),
        ('Payment Tracking', {
            'fields': (
                'amount_paid',
                'outstanding_balance',
                'amount_disbursed',
                'payment_progress_bar',
                'days_overdue_display',
            )
        }),
        ('Purpose & Details', {
            'fields': (
                'purpose',
                'purpose_details',
            )
        }),
        ('Collateral (Optional)', {
            'fields': (
                'collateral_type',
                'collateral_value',
                'collateral_description',
            ),
            'classes': ('collapse',),
        }),
        ('Guarantors', {
            'fields': (
                ('guarantor_name', 'guarantor_phone'),
                'guarantor_address',
                ('guarantor2_name', 'guarantor2_phone'),
                'guarantor2_address',
            )
        }),
        ('Disbursement Details', {
            'fields': (
                'disbursement_method',
                'bank_name',
                'bank_account_number',
                'bank_account_name',
                'disbursement_reference',
                'disbursement_notes',
            ),
            'classes': ('collapse',),
        }),
        ('Important Dates', {
            'fields': (
                'application_date',
                'approval_date',
                'disbursement_date',
                'first_repayment_date',
                'final_repayment_date',
                'next_repayment_date',
                'completion_date',
            )
        }),
        ('Rejection (if applicable)', {
            'fields': (
                'rejection_reason',
            ),
            'classes': ('collapse',),
        }),
        ('System Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    # Ordering
    ordering = ['-application_date']
    
    # Date hierarchy
    date_hierarchy = 'application_date'
    
    # Actions
    actions = ['approve_loans', 'mark_as_overdue']
    
    def client_name_link(self, obj):
        """Display client name as a link to client detail"""
        if obj.client:
            url = reverse('admin:app_user_change', args=[obj.client.pk])
            return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
        return '-'
    client_name_link.short_description = 'Client'
    
    def principal_amount_formatted(self, obj):
        """Format principal amount with currency"""
        return f'₦{obj.principal_amount:,.2f}'
    principal_amount_formatted.short_description = 'Principal'
    principal_amount_formatted.admin_order_field = 'principal_amount'
    
    def outstanding_balance_formatted(self, obj):
        """Format outstanding balance with currency"""
        return f'₦{obj.outstanding_balance:,.2f}'
    outstanding_balance_formatted.short_description = 'Balance'
    outstanding_balance_formatted.admin_order_field = 'outstanding_balance'
    
    def status_colored(self, obj):
        """Display status with color coding"""
        colors = {
            'pending_approval': '#FFA500',  # Orange
            'approved': '#FFD700',          # Gold
            'rejected': '#DC143C',          # Crimson
            'active': '#32CD32',            # Lime Green
            'overdue': '#FF0000',           # Red
            'completed': '#008000',         # Green
        }
        color = colors.get(obj.status, '#808080')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Status'
    status_colored.admin_order_field = 'status'
    
    def days_overdue_display(self, obj):
        """Display days overdue if applicable"""
        days = obj.days_overdue
        if days > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">{} days</span>',
                days
            )
        return '-'
    days_overdue_display.short_description = 'Days Overdue'
    
    def payment_progress_bar(self, obj):
        """Display payment progress as a visual bar"""
        if obj.total_repayment > 0:
            progress = (obj.amount_paid / obj.total_repayment) * 100
            progress = min(progress, 100)  # Cap at 100%
            
            # Color based on progress
            if progress >= 100:
                color = '#008000'  # Green
            elif progress >= 75:
                color = '#32CD32'  # Lime Green
            elif progress >= 50:
                color = '#FFD700'  # Gold
            elif progress >= 25:
                color = '#FFA500'  # Orange
            else:
                color = '#DC143C'  # Crimson
            
            return format_html(
                '<div style="width: 200px; background-color: #f0f0f0; border-radius: 5px;">'
                '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 5px; text-align: center; color: white; font-weight: bold;">'
                '{:.1f}%'
                '</div></div>',
                progress, color, progress
            )
        return '-'
    payment_progress_bar.short_description = 'Payment Progress'
    
    def approve_loans(self, request, queryset):
        """Bulk approve selected loans"""
        count = 0
        for loan in queryset.filter(status='pending_approval'):
            success, message = loan.approve(approved_by=request.user)
            if success:
                count += 1
        
        self.message_user(request, f'{count} loan(s) approved successfully.')
    approve_loans.short_description = 'Approve selected loans'
    
    def mark_as_overdue(self, request, queryset):
        """Bulk mark selected loans as overdue"""
        count = queryset.filter(
            status='active',
            next_repayment_date__lt=timezone.now().date()
        ).update(status='overdue')
        
        self.message_user(request, f'{count} loan(s) marked as overdue.')
    mark_as_overdue.short_description = 'Mark as overdue'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('client', 'branch', 'created_by', 'approved_by', 'disbursed_by')
    
    def has_delete_permission(self, request, obj=None):
        """Only admins can delete loans"""
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'user_role'):
            return request.user.user_role == 'admin'
        return False
    
    def save_model(self, request, obj, form, change):
        """Override save to set created_by on creation"""
        if not change:  # If creating new loan
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Register the admin
admin.site.register(Loan, LoanAdmin)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_ref', 'transaction_type_display', 'client_link',
        'amount_display', 'status_badge', 'transaction_date', 'branch'
    ]
    list_filter = [
        'transaction_type', 'status', 'branch', 'transaction_date'
    ]
    search_fields = [
        'transaction_ref', 'client__email', 'client__first_name',
        'client__last_name', 'description'
    ]
    raw_id_fields = ['client', 'savings_account', 'loan', 'branch', 'processed_by']
    readonly_fields = [
        'id', 'transaction_ref', 'balance_before', 'balance_after',
        'transaction_date', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_ref', 'transaction_type', 'status', 'amount')
        }),
        ('Related Accounts', {
            'fields': ('client', 'savings_account', 'loan', 'branch')
        }),
        ('Balance Tracking', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Processing', {
            'fields': ('processed_by', 'transaction_date')
        }),
        ('Description', {
            'fields': ('description', 'notes')
        }),
        ('Reversal', {
            'fields': ('reversed_transaction',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def client_link(self, obj):
        url = reverse('admin:app_user_change', args=[obj.client.id])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())
    client_link.short_description = 'Client'
    
    def transaction_type_display(self, obj):
        return obj.get_transaction_type_display()
    transaction_type_display.short_description = 'Type'
    
    def amount_display(self, obj):
        from decimal import Decimal
        color = 'green' if obj.transaction_type in ['deposit', 'loan_disbursement', 'interest'] else 'red'
        try:
            # Convert amount to Decimal to handle any type issues
            amount = Decimal(str(obj.amount))
            return format_html(
                '<span style="color: {};">₦{:,.2f}</span>',
                color, amount
            )
        except (ValueError, TypeError, AttributeError):
            # Fallback if amount is None or invalid
            return format_html('<span style="color: {};">₦0.00</span>', color)
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'reversed': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user_link', 'notification_type_display',
        'is_read_badge', 'is_urgent_badge', 'created_at'
    ]
    list_filter = [
        'notification_type', 'is_read', 'is_urgent', 'created_at'
    ]
    search_fields = [
        'title', 'message', 'user__email', 'user__first_name', 'user__last_name'
    ]
    raw_id_fields = ['user', 'related_client', 'related_loan', 'related_savings']
    readonly_fields = ['id', 'read_at', 'created_at']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        ('Related Items', {
            'fields': ('related_client', 'related_loan', 'related_savings')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'is_urgent')
        }),
        ('System Information', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def user_link(self, obj):
        url = reverse('admin:app_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name())
    user_link.short_description = 'Recipient'
    
    def notification_type_display(self, obj):
        return obj.get_notification_type_display()
    notification_type_display.short_description = 'Type'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color: gray;">✓ Read</span>')
        return format_html('<span style="color: green; font-weight: bold;">● Unread</span>')
    is_read_badge.short_description = 'Status'
    
    def is_urgent_badge(self, obj):
        if obj.is_urgent:
            return format_html('<span style="color: red; font-weight: bold;">🔴 Urgent</span>')
        return '—'
    is_urgent_badge.short_description = 'Priority'
    
    def mark_as_read(self, request, queryset):
        updated = queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{updated} notification(s) marked as read.')
    mark_as_read.short_description = 'Mark as read'
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
    mark_as_unread.short_description = 'Mark as unread'







