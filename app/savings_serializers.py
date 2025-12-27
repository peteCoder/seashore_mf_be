"""
Savings Account Serializers
Serializers for savings account operations (NO INTEREST - as per requirements)
"""

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from .models import SavingsAccount, User, Transaction
from django.db.models import Sum


class SavingsAccountCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating savings accounts
    """
    client_id = serializers.UUIDField(required=True, write_only=True)
    branch_id = serializers.UUIDField(required=False, write_only=True)
    
    class Meta:
        model = SavingsAccount
        fields = [
            'account_type', 'minimum_balance',
            'client_id', 'branch_id', 'notes'
        ]
    
    def validate_minimum_balance(self, value):
        """Validate minimum balance is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Minimum balance cannot be negative.")
        return value
    
    def validate(self, data):
        """Validate client exists and has no duplicate account type"""
        client_id = data.get('client_id')
        account_type = data.get('account_type')
        
        try:
            client = User.objects.get(id=client_id, user_role='client')
            
            # Check if client already has this account type
            existing = SavingsAccount.objects.filter(
                client=client,
                account_type=account_type,
                status__in=['pending', 'active']
            ).exists()
            
            if existing:
                raise serializers.ValidationError({
                    'account_type': f'Client already has an active {account_type} savings account.'
                })
            
            data['client'] = client
            data['branch'] = client.branch
            
        except User.DoesNotExist:
            raise serializers.ValidationError({'client_id': 'Client not found.'})
        
        return data
    
    def create(self, validated_data):
        # Remove write-only fields
        client = validated_data.pop('client')
        branch = validated_data.pop('branch')
        validated_data.pop('client_id')
        if 'branch_id' in validated_data:
            validated_data.pop('branch_id')
        
        # Generate account number
        account_number = f"SA{timezone.now().strftime('%Y%m%d')}{SavingsAccount.objects.count() + 1:08d}"
        
        # Get created_by from context
        created_by = self.context.get('request').user if self.context.get('request') else None
        
        # Create savings account with status='pending'
        savings_account = SavingsAccount.objects.create(
            account_number=account_number,
            client=client,
            branch=branch,
            created_by=created_by,
            status='pending',
            balance=Decimal('0.00'),
            **validated_data
        )
        
        return savings_account


class SavingsAccountDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for savings account information
    """
    client_name = serializers.SerializerMethodField()
    client_email = serializers.SerializerMethodField()
    client_phone = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    account_type_display = serializers.SerializerMethodField()

    total_deposits = serializers.SerializerMethodField()
    total_withdrawals = serializers.SerializerMethodField()
    interest_earned = serializers.SerializerMethodField()
    
    class Meta:
        model = SavingsAccount
        fields = '__all__'
    
    def get_client_name(self, obj):
        return obj.client.get_full_name()
    
    def get_client_email(self, obj):
        return obj.client.email
    
    def get_client_phone(self, obj):
        return obj.client.phone
    
    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None
    
    def get_approved_by_name(self, obj):
        return obj.approved_by.get_full_name() if obj.approved_by else None
    
    def get_account_type_display(self, obj):
        return obj.get_account_type_display()
    
    def get_total_deposits(self, obj):
        """Calculate total deposits from transactions"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='deposit',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        
        return float(total) if total else 0.00

    def get_total_withdrawals(self, obj):
        """Calculate total withdrawals from transactions"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        
        return float(total) if total else 0.00

    def get_interest_earned(self, obj):
        """Calculate total interest earned"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='interest',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        
        return float(total) if total else 0.00


class SavingsAccountListSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for savings account list views
    """
    client_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    account_type_display = serializers.SerializerMethodField()

    total_deposits = serializers.SerializerMethodField()  # ADD
    total_withdrawals = serializers.SerializerMethodField()  # ADD
    interest_earned = serializers.SerializerMethodField()  # ADD
    
    class Meta:
        model = SavingsAccount
        fields = [
            'id', 'account_number', 'client', 'client_name',
            'branch', 'branch_name', 'account_type', 'account_type_display',
            'balance', 'status', 'date_opened', 'minimum_balance',
            'total_deposits', 'total_withdrawals', 'interest_earned',  # ADD
        ]
    
    def get_client_name(self, obj):
        return obj.client.get_full_name()
    
    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else None
    
    def get_account_type_display(self, obj):
        return obj.get_account_type_display()
    
    # ADD THESE THREE METHODS
    def get_total_deposits(self, obj):
        """Calculate total deposits from transactions"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='deposit',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        return float(total) if total else 0.00
    
    def get_total_withdrawals(self, obj):
        """Calculate total withdrawals from transactions"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        return float(total) if total else 0.00
    
    def get_interest_earned(self, obj):
        """Calculate total interest earned"""
        total = Transaction.objects.filter(
            savings_account=obj,
            transaction_type='interest',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum']
        return float(total) if total else 0.00



class SavingsAccountApprovalSerializer(serializers.Serializer):
    """
    Serializer for savings account approval/rejection
    """
    action = serializers.ChoiceField(choices=['approve', 'reject'], required=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate rejection reason is provided when rejecting"""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting an account.'
            })
        return data


class DepositSerializer(serializers.Serializer):
    """
    Serializer for savings account deposit
    """
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    transaction_date = serializers.DateField(default=timezone.now().date())
    payment_method = serializers.ChoiceField(
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('mobile_money', 'Mobile Money'),
            ('cheque', 'Cheque')
        ],
        default='cash'
    )
    payment_reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate deposit amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Deposit amount must be greater than zero.")
        return value


class WithdrawalSerializer(serializers.Serializer):
    """
    Serializer for savings account withdrawal
    """
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    transaction_date = serializers.DateField(default=timezone.now().date())
    payment_method = serializers.ChoiceField(
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('mobile_money', 'Mobile Money'),
            ('cheque', 'Cheque')
        ],
        default='cash'
    )
    payment_reference = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_amount(self, value):
        """Validate withdrawal amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Withdrawal amount must be greater than zero.")
        return value
    
    def validate(self, data):
        """Validate withdrawal against account balance"""
        savings_account = self.context.get('savings_account')
        
        if savings_account:
            can_withdraw, message = savings_account.can_withdraw(data['amount'])
            if not can_withdraw:
                raise serializers.ValidationError({'amount': message})
        
        return data