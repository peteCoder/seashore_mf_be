"""
Loan Serializers
Comprehensive serializers for loan application, approval, disbursement, and repayment
Clean implementation with proper validation and error handling
"""

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class LoanApplicationSerializer(serializers.Serializer):
    """
    Serializer for loan application with automatic calculation.
    Staff enters: principal, frequency, duration, and purpose.
    System calculates: interest, total amount, installments automatically.
    """
    # Required input fields
    client_id = serializers.UUIDField(required=True)
    principal_amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=True,
        min_value=Decimal('1000.00')
    )
    repayment_frequency = serializers.ChoiceField(
        choices=['daily', 'weekly', 'biweekly', 'monthly'],
        required=True
    )
    duration_value = serializers.IntegerField(required=True, min_value=1)
    purpose = serializers.CharField(required=True, max_length=200)
    
    # Optional fields
    purpose_details = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # Collateral (optional)
    collateral_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    collateral_value = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False, 
        allow_null=True
    )
    collateral_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # Guarantor 1 (required)
    guarantor_name = serializers.CharField(required=True, max_length=200)
    guarantor_phone = serializers.CharField(required=True, max_length=20)
    guarantor_address = serializers.CharField(required=True)
    
    # Guarantor 2 (required)
    guarantor2_name = serializers.CharField(required=True, max_length=200)
    guarantor2_phone = serializers.CharField(required=True, max_length=20)
    guarantor2_address = serializers.CharField(required=True)
    
    def validate_principal_amount(self, value):
        """Validate principal amount"""
        if value < Decimal('1000.00'):
            raise serializers.ValidationError("Minimum loan amount is ₦1,000.00")
        if value > Decimal('100000000.00'):  # 100 million max
            raise serializers.ValidationError("Maximum loan amount is ₦100,000,000.00")
        return value
    
    def validate_duration_value(self, value):
        """Validate duration value"""
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than zero")
        if value > 1000:  # Reasonable limit
            raise serializers.ValidationError("Duration value too large")
        return value
    
    def validate(self, data):
        """Validate loan application and check client eligibility"""
        from .models import User
        
        client_id = data.get('client_id')
        principal_amount = data.get('principal_amount')
        
        # Validate client exists and is a client
        try:
            client = User.objects.get(id=client_id, user_role='client')
            
            # Check if client is approved
            if not client.is_approved:
                raise serializers.ValidationError({
                    'client_id': 'Client must be approved before applying for a loan.'
                })
            
            # Check if client is active
            if not client.is_active:
                raise serializers.ValidationError({
                    'client_id': 'Client account is not active.'
                })
            
            # Check tier limits
            if hasattr(client, 'client_profile'):
                if not client.client_profile.can_borrow(principal_amount):
                    loan_limit = client.client_profile.get_loan_limit()
                    raise serializers.ValidationError({
                        'principal_amount': f'Loan amount exceeds tier limit of ₦{loan_limit:,.2f}. '
                                          f'Current tier: {client.client_profile.get_level_display()}.'
                    })
            
            # Store for create method
            data['_client'] = client
            data['_branch'] = client.branch
            
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'client_id': 'Client not found or not a valid client account.'
            })
        
        return data
    
    def create(self, validated_data):
        """Create loan with automatic calculation"""
        from .models import Loan
        
        # Extract internal data
        client = validated_data.pop('_client')
        branch = validated_data.pop('_branch')
        
        # Generate loan number
        loan_number = f"LN{timezone.now().strftime('%Y%m%d')}{Loan.objects.count() + 1:06d}"
        
        # Get created_by from context
        request = self.context.get('request')
        created_by = request.user if request else None
        
        # Create loan - model's save() will calculate amounts
        loan = Loan.objects.create(
            loan_number=loan_number,
            client=client,
            branch=branch,
            created_by=created_by,
            status='pending_approval',
            principal_amount=validated_data['principal_amount'],
            repayment_frequency=validated_data['repayment_frequency'],
            duration_value=validated_data['duration_value'],
            purpose=validated_data['purpose'],
            purpose_details=validated_data.get('purpose_details', ''),
            collateral_type=validated_data.get('collateral_type', ''),
            collateral_value=validated_data.get('collateral_value'),
            collateral_description=validated_data.get('collateral_description', ''),
            guarantor_name=validated_data['guarantor_name'],
            guarantor_phone=validated_data['guarantor_phone'],
            guarantor_address=validated_data['guarantor_address'],
            guarantor2_name=validated_data['guarantor2_name'],
            guarantor2_phone=validated_data['guarantor2_phone'],
            guarantor2_address=validated_data['guarantor2_address'],
        )
        
        return loan


class LoanCalculationPreviewSerializer(serializers.Serializer):
    """
    Serializer for previewing loan calculation before submission.
    Used in the frontend to show live calculations.
    """
    principal_amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=True,
        min_value=Decimal('1.00')
    )
    repayment_frequency = serializers.ChoiceField(
        choices=['daily', 'weekly', 'biweekly', 'monthly'],
        required=True
    )
    duration_value = serializers.IntegerField(required=True, min_value=1)
    
    def validate(self, data):
        """Calculate and return loan details"""
        from .loan_calculator import LoanCalculator
        
        try:
            calc_result = LoanCalculator.calculate_loan(
                principal_amount=data['principal_amount'],
                frequency=data['repayment_frequency'],
                duration_value=data['duration_value']
            )
            
            # Return calculation as the validated data
            return calc_result
            
        except ValueError as e:
            raise serializers.ValidationError({'error': str(e)})
        except Exception as e:
            raise serializers.ValidationError({'error': 'Calculation failed. Please check your input values.'})


class LoanListSerializer(serializers.Serializer):
    """Serializer for loan list views with essential fields"""
    
    # Basic identification
    id = serializers.UUIDField()
    loan_number = serializers.CharField()
    status = serializers.CharField()
    
    # Client info
    client_id = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    
    # Branch
    branch_name = serializers.SerializerMethodField()
    
    # Amounts
    principal_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_repayment = serializers.DecimalField(max_digits=15, decimal_places=2)
    installment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Loan details
    repayment_frequency = serializers.CharField()
    duration_value = serializers.IntegerField()
    monthly_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=4)
    annual_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    
    # Dates
    application_date = serializers.DateTimeField()
    disbursement_date = serializers.DateTimeField(allow_null=True)
    next_repayment_date = serializers.DateField(allow_null=True)
    
    # Computed
    days_overdue = serializers.IntegerField()
    
    # Legacy fields for backward compatibility
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, source='outstanding_balance')
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    loan_term = serializers.IntegerField()
    payment_frequency = serializers.CharField()
    created_at = serializers.DateTimeField()
    
    def get_client_id(self, obj):
        return str(obj.client.id) if obj.client else None
    
    def get_client_name(self, obj):
        return obj.client.get_full_name() if obj.client else "N/A"
    
    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else "N/A"


class LoanDetailSerializer(serializers.Serializer):
    """Comprehensive serializer for detailed loan information"""
    
    # Basic identification
    id = serializers.UUIDField()
    loan_number = serializers.CharField()
    status = serializers.CharField()
    
    # Client information
    client_id = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    client_email = serializers.SerializerMethodField()
    client_phone = serializers.SerializerMethodField()
    
    # Branch
    branch_name = serializers.SerializerMethodField()
    
    # Staff information
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    disbursed_by_name = serializers.SerializerMethodField()
    
    # Core loan details (input)
    principal_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    repayment_frequency = serializers.CharField()
    duration_value = serializers.IntegerField()
    
    # Calculated fields
    monthly_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=4)
    annual_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    duration_months = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_interest = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_repayment = serializers.DecimalField(max_digits=15, decimal_places=2)
    installment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    number_of_installments = serializers.IntegerField()
    
    # Payment tracking
    amount_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    amount_disbursed = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    # Purpose
    purpose = serializers.CharField()
    purpose_details = serializers.CharField(allow_blank=True, allow_null=True)
    
    # Collateral
    collateral_type = serializers.CharField(allow_blank=True, allow_null=True)
    collateral_value = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True)
    collateral_description = serializers.CharField(allow_blank=True, allow_null=True)
    
    # Guarantors
    guarantor_name = serializers.CharField()
    guarantor_phone = serializers.CharField()
    guarantor_address = serializers.CharField()
    guarantor2_name = serializers.CharField()
    guarantor2_phone = serializers.CharField()
    guarantor2_address = serializers.CharField()
    
    # Dates
    application_date = serializers.DateTimeField()
    approval_date = serializers.DateTimeField(allow_null=True)
    disbursement_date = serializers.DateTimeField(allow_null=True)
    first_repayment_date = serializers.DateField(allow_null=True)
    final_repayment_date = serializers.DateField(allow_null=True)
    next_repayment_date = serializers.DateField(allow_null=True)
    completion_date = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    
    # Disbursement details
    disbursement_method = serializers.CharField(allow_blank=True, allow_null=True)
    bank_name = serializers.CharField(allow_blank=True, allow_null=True)
    bank_account_number = serializers.CharField(allow_blank=True, allow_null=True)
    bank_account_name = serializers.CharField(allow_blank=True, allow_null=True)
    disbursement_reference = serializers.CharField(allow_blank=True, allow_null=True)
    disbursement_notes = serializers.CharField(allow_blank=True, allow_null=True)
    
    # Rejection
    rejection_reason = serializers.CharField(allow_blank=True, allow_null=True)
    
    # Computed fields
    days_overdue = serializers.IntegerField()
    
    # Legacy fields for backward compatibility
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, source='outstanding_balance')
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    loan_term = serializers.IntegerField()
    payment_frequency = serializers.CharField()
    
    # Methods for computed fields
    def get_client_id(self, obj):
        return str(obj.client.id) if obj.client else None
    
    def get_client_name(self, obj):
        return obj.client.get_full_name() if obj.client else "N/A"
    
    def get_client_email(self, obj):
        return obj.client.email if obj.client else None
    
    def get_client_phone(self, obj):
        return obj.client.phone if obj.client else None
    
    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else "N/A"
    
    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None
    
    def get_approved_by_name(self, obj):
        return obj.approved_by.get_full_name() if obj.approved_by else None
    
    def get_disbursed_by_name(self, obj):
        return obj.disbursed_by.get_full_name() if obj.disbursed_by else None


class LoanApprovalSerializer(serializers.Serializer):
    """Serializer for loan approval/rejection"""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'], required=True)
    rejection_reason = serializers.CharField(
        required=False, 
        allow_blank=True, 
        allow_null=True,
        max_length=1000
    )
    
    def validate(self, data):
        """Validate rejection reason is provided when rejecting"""
        if data['action'] == 'reject':
            if not data.get('rejection_reason'):
                raise serializers.ValidationError({
                    'rejection_reason': 'Rejection reason is required when rejecting a loan.'
                })
        return data


class LoanDisbursementSerializer(serializers.Serializer):
    """Serializer for loan disbursement"""
    
    disbursement_date = serializers.DateField(required=False, allow_null=True)
    disbursement_method = serializers.ChoiceField(
        choices=['bank_transfer', 'cash', 'mobile_money', 'cheque'],
        required=True
    )
    
    # Bank details (required for bank_transfer)
    bank_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    account_number = serializers.CharField(required=False, allow_blank=True, max_length=50)
    account_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    
    # Optional fields
    transaction_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    disbursement_notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    
    def validate(self, data):
        """Validate bank details for bank transfer"""
        if data.get('disbursement_method') == 'bank_transfer':
            if not data.get('bank_name'):
                raise serializers.ValidationError({
                    'bank_name': 'Bank name is required for bank transfer.'
                })
            if not data.get('account_number'):
                raise serializers.ValidationError({
                    'account_number': 'Account number is required for bank transfer.'
                })
            if not data.get('account_name'):
                raise serializers.ValidationError({
                    'account_name': 'Account name is required for bank transfer.'
                })
        
        # Set default disbursement date if not provided
        if not data.get('disbursement_date'):
            data['disbursement_date'] = timezone.now().date()
        
        return data


class LoanRepaymentSerializer(serializers.Serializer):
    """Serializer for loan repayment recording"""
    
    amount = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=True,
        min_value=Decimal('0.01')
    )
    payment_date = serializers.DateField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=['cash', 'bank_transfer', 'mobile_money', 'cheque', 'pos'],
        default='cash'
    )
    reference_number = serializers.CharField(
        required=False, 
        allow_blank=True, 
        max_length=100
    )
    payment_notes = serializers.CharField(
        required=False, 
        allow_blank=True, 
        max_length=1000
    )
    
    def validate_amount(self, value):
        """Validate repayment amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Repayment amount must be greater than zero")
        return value
    
    def validate(self, data):
        """Validate repayment against loan balance"""
        loan = self.context.get('loan')
        
        # Set default payment date if not provided
        if not data.get('payment_date'):
            data['payment_date'] = timezone.now().date()
        
        # Validate against outstanding balance
        if loan and data['amount'] > loan.outstanding_balance:
            raise serializers.ValidationError({
                'amount': f'Repayment amount (₦{data["amount"]:,.2f}) exceeds outstanding balance (₦{loan.outstanding_balance:,.2f})'
            })
        
        return data


class RepaymentScheduleItemSerializer(serializers.Serializer):
    """Serializer for individual repayment schedule item"""
    
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    installment_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance_after_payment = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    
    # Optional tracking fields
    amount_paid = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False,
        default=Decimal('0.00')
    )
    payment_date = serializers.DateField(required=False, allow_null=True)
    days_overdue = serializers.IntegerField(required=False, default=0)