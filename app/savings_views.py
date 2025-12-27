"""
Savings Account Views
Complete CRUD operations and transaction workflows
NO INTEREST CALCULATION - as per requirements
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db import models
from decimal import Decimal

from .models import SavingsAccount, User, Transaction, Notification
from .savings_serializers import (
    SavingsAccountCreateSerializer,
    SavingsAccountDetailSerializer,
    SavingsAccountListSerializer,
    SavingsAccountApprovalSerializer,
    DepositSerializer,
    WithdrawalSerializer,
)
from .permissions import (
    IsStaffOrAbove,
    IsManagerOrAbove,
    CanApproveSavingsAccount,
    CanAccessSavingsAccount
)


class SavingsAccountCreateView(generics.CreateAPIView):
    """
    Create new savings account for client
    Staff and above can create accounts
    """
    serializer_class = SavingsAccountCreateSerializer
    permission_classes = [IsStaffOrAbove]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        savings_account = serializer.save()
        
        # Create notification for managers
        managers = User.objects.filter(
            user_role__in=['manager', 'director', 'admin'],
            branch=savings_account.branch,
            is_active=True
        )
        
        for manager in managers:
            Notification.objects.create(
                user=manager,
                notification_type='savings_created',
                title='New Savings Account Created',
                message=f'{savings_account.client.get_full_name()} has opened a {savings_account.get_account_type_display()} account.',
                is_urgent=True,
                related_savings=savings_account,
                related_client=savings_account.client
            )
        
        return Response({
            'success': True,
            'message': 'Savings account created successfully. Awaiting approval.',
            'account': SavingsAccountDetailSerializer(savings_account).data
        }, status=status.HTTP_201_CREATED)


class SavingsAccountListView(generics.ListAPIView):
    """
    List all savings accounts with filtering
    Admin/Director: See all accounts
    Manager: See accounts in their branch
    Staff: See accounts in their branch
    """
    serializer_class = SavingsAccountListSerializer
    permission_classes = [IsStaffOrAbove]
    
    def get_queryset(self):
        user = self.request.user
        
        # Base queryset
        if user.user_role in ['admin', 'director']:
            queryset = SavingsAccount.objects.all()
        else:
            queryset = SavingsAccount.objects.filter(branch=user.branch)
        
        # Apply filters from query params
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        account_type = self.request.query_params.get('account_type')
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client__id=client_id)
        
        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(branch__id=branch_id)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(account_number__icontains=search) |
                Q(client__first_name__icontains=search) |
                Q(client__last_name__icontains=search) |
                Q(client__email__icontains=search)
            )
        
        return queryset.select_related('client', 'branch', 'created_by').order_by('-date_opened')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        # Return array directly - apiCall will wrap it in {success: true, data: [...]}
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
class SavingsAccountDetailView(generics.RetrieveAPIView):
    """
    Get detailed savings account information
    """
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingsAccountDetailSerializer
    permission_classes = [CanAccessSavingsAccount]
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Return serializer.data directly - apiCall will wrap it
        return Response(serializer.data, status=status.HTTP_200_OK)


class SavingsAccountStatusUpdateView(APIView):
    """
    Update savings account status
    Managers and above can update status
    """
    permission_classes = [CanApproveSavingsAccount]
    
    def patch(self, request, account_id):
        try:
            account = SavingsAccount.objects.get(id=account_id)
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Savings account not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not CanAccessSavingsAccount().has_object_permission(request, self, account):
            return Response({
                'success': False,
                'message': 'You do not have permission to update this account.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        new_status = request.data.get('status')
        
        # Validate status
        valid_statuses = ['active', 'suspended', 'closed', 'pending']
        if new_status not in valid_statuses:
            return Response({
                'success': False,
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = account.status
        account.status = new_status
        
        # If activating a pending account, set approval info
        if new_status == 'active' and old_status == 'pending':
            account.approved_by = request.user
            account.date_approved = timezone.now()
        
        account.save()
        
        # Create notification
        if account.created_by:
            Notification.objects.create(
                user=account.created_by,
                notification_type='savings_status_changed',
                title='Savings Account Status Updated',
                message=f'Account {account.account_number} status changed from {old_status} to {new_status}.',
                related_savings=account
            )
        
        return Response({
            'success': True,
            'message': f'Account status updated to {new_status}.',
            'account': SavingsAccountDetailSerializer(account).data
        }, status=status.HTTP_200_OK)


class SavingsAccountApprovalView(APIView):
    """
    Approve or reject savings account
    Managers and above can approve
    """
    permission_classes = [CanApproveSavingsAccount]
    
    def post(self, request, account_id):
        try:
            account = SavingsAccount.objects.get(id=account_id)
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Savings account not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission for this specific account
        if not CanAccessSavingsAccount().has_object_permission(request, self, account):
            return Response({
                'success': False,
                'message': 'You do not have permission to approve this account.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate account status
        if account.status != 'pending':
            return Response({
                'success': False,
                'message': f'Account cannot be approved. Current status: {account.get_status_display()}.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SavingsAccountApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        
        if action == 'approve':
            # Approve account
            account.status = 'active'
            account.approved_by = request.user
            account.date_approved = timezone.now()
            account.save()
            
            # Notify staff who created the account
            if account.created_by:
                Notification.objects.create(
                    user=account.created_by,
                    notification_type='savings_approved',
                    title='Savings Account Approved',
                    message=f'Savings account {account.account_number} for {account.client.get_full_name()} has been approved.',
                    related_savings=account
                )
            
            message = 'Savings account approved successfully.'
            
        else:  # reject
            account.status = 'closed'
            account.notes += f"\n\nRejection Reason: {serializer.validated_data.get('rejection_reason', '')}"
            account.save()
            
            # Notify staff who created the account
            if account.created_by:
                Notification.objects.create(
                    user=account.created_by,
                    notification_type='savings_rejected',
                    title='Savings Account Rejected',
                    message=f'Savings account {account.account_number} for {account.client.get_full_name()} has been rejected.',
                    related_savings=account
                )
            
            message = 'Savings account rejected.'
        
        return Response({
            'success': True,
            'message': message,
            'account': SavingsAccountDetailSerializer(account).data
        }, status=status.HTTP_200_OK)


class DepositView(APIView):
    """
    Record deposit to savings account (creates pending transaction for approval)
    Staff and above can record deposits, but they require manager+ approval
    """
    permission_classes = [IsStaffOrAbove]
    
    def post(self, request, account_id):
        try:
            account = SavingsAccount.objects.get(id=account_id)
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Savings account not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not CanAccessSavingsAccount().has_object_permission(request, self, account):
            return Response({
                'success': False,
                'message': 'You do not have permission to process deposits for this account.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate account status
        if account.status != 'active':
            return Response({
                'success': False,
                'message': f'Cannot deposit to account with status: {account.get_status_display()}.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data['amount']
        balance_before = account.balance
        
        # Create PENDING transaction (balance will be updated on approval)
        transaction_ref = f"DEP{timezone.now().strftime('%Y%m%d%H%M%S')}{account.id.hex[:6]}"
        transaction = Transaction.objects.create(
            transaction_ref=transaction_ref,
            transaction_type='deposit',
            amount=amount,
            client=account.client,
            savings_account=account,
            branch=account.branch,
            processed_by=request.user,
            balance_before=balance_before,
            balance_after=None,  # Will be set on approval
            description=f'Deposit to {account.account_number}',
            notes=serializer.validated_data.get('notes', ''),
            status='pending'  # Requires approval
        )
        
        # Notify managers/directors/admins about pending transaction
        managers = User.objects.filter(
            user_role__in=['manager', 'director', 'admin'],
            is_active=True,
            branch=account.branch
        )
        
        for manager in managers:
            Notification.objects.create(
                user=manager,
                notification_type='deposit_pending',
                title='Deposit Pending Approval',
                message=f'A deposit of ₦{amount:,.2f} for {account.client.get_full_name()} ({account.account_number}) requires your approval. Requested by {request.user.get_full_name()}.',
                related_savings=account
            )
        
        # Also notify directors/admins who may not be branch-specific
        head_office_staff = User.objects.filter(
            user_role__in=['director', 'admin'],
            is_active=True
        ).exclude(branch=account.branch)
        
        for staff in head_office_staff:
            Notification.objects.create(
                user=staff,
                notification_type='deposit_pending',
                title='Deposit Pending Approval',
                message=f'A deposit of ₦{amount:,.2f} for {account.client.get_full_name()} ({account.account_number}) at {account.branch.name} requires approval. Requested by {request.user.get_full_name()}.',
                related_savings=account
            )
        
        return Response({
            'success': True,
            'message': 'Deposit request submitted successfully. Awaiting approval from a manager.',
            'transaction_id': str(transaction.id),
            'transaction_ref': transaction_ref,
            'amount': float(amount),
            'status': 'pending',
            'requires_approval': True
        }, status=status.HTTP_201_CREATED)


class WithdrawalView(APIView):
    """
    Record withdrawal from savings account (creates pending transaction for approval)
    Staff and above can record withdrawals, but they require manager+ approval
    """
    permission_classes = [IsStaffOrAbove]
    
    def post(self, request, account_id):
        try:
            account = SavingsAccount.objects.get(id=account_id)
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Savings account not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if not CanAccessSavingsAccount().has_object_permission(request, self, account):
            return Response({
                'success': False,
                'message': 'You do not have permission to process withdrawals for this account.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate account status
        if account.status != 'active':
            return Response({
                'success': False,
                'message': f'Cannot withdraw from account with status: {account.get_status_display()}.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = WithdrawalSerializer(data=request.data, context={'savings_account': account})
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data['amount']
        
        # Validate withdrawal is allowed (check balance, etc.)
        can_withdraw, message = account.can_withdraw(amount)
        if not can_withdraw:
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for pending withdrawals that might affect balance
        pending_withdrawals = Transaction.objects.filter(
            savings_account=account,
            transaction_type='withdrawal',
            status='pending'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        available_balance = account.balance - pending_withdrawals
        if amount > available_balance:
            return Response({
                'success': False,
                'message': f'Insufficient available balance. Current balance: ₦{account.balance:,.2f}, Pending withdrawals: ₦{pending_withdrawals:,.2f}, Available: ₦{available_balance:,.2f}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        balance_before = account.balance
        
        # Create PENDING transaction (balance will be updated on approval)
        transaction_ref = f"WDL{timezone.now().strftime('%Y%m%d%H%M%S')}{account.id.hex[:6]}"
        transaction = Transaction.objects.create(
            transaction_ref=transaction_ref,
            transaction_type='withdrawal',
            amount=amount,
            client=account.client,
            savings_account=account,
            branch=account.branch,
            processed_by=request.user,
            balance_before=balance_before,
            balance_after=None,  # Will be set on approval
            description=f'Withdrawal from {account.account_number}',
            notes=serializer.validated_data.get('notes', ''),
            status='pending'  # Requires approval
        )
        
        # Notify managers/directors/admins about pending transaction
        managers = User.objects.filter(
            user_role__in=['manager', 'director', 'admin'],
            is_active=True,
            branch=account.branch
        )
        
        for manager in managers:
            Notification.objects.create(
                user=manager,
                notification_type='withdrawal_pending',
                title='Withdrawal Pending Approval',
                message=f'A withdrawal of ₦{amount:,.2f} from {account.client.get_full_name()} ({account.account_number}) requires your approval. Requested by {request.user.get_full_name()}.',
                related_savings=account
            )
        
        # Also notify directors/admins who may not be branch-specific
        head_office_staff = User.objects.filter(
            user_role__in=['director', 'admin'],
            is_active=True
        ).exclude(branch=account.branch)
        
        for staff in head_office_staff:
            Notification.objects.create(
                user=staff,
                notification_type='withdrawal_pending',
                title='Withdrawal Pending Approval',
                message=f'A withdrawal of ₦{amount:,.2f} from {account.client.get_full_name()} ({account.account_number}) at {account.branch.name} requires approval. Requested by {request.user.get_full_name()}.',
                related_savings=account
            )
        
        return Response({
            'success': True,
            'message': 'Withdrawal request submitted successfully. Awaiting approval from a manager.',
            'transaction_id': str(transaction.id),
            'transaction_ref': transaction_ref,
            'amount': float(amount),
            'status': 'pending',
            'requires_approval': True
        }, status=status.HTTP_201_CREATED)


class SavingsStatisticsView(APIView):
    """
    Get savings statistics for dashboard
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Filter accounts based on role
        if user.user_role in ['admin', 'director']:
            accounts = SavingsAccount.objects.all()
            transactions = Transaction.objects.filter(transaction_type__in=['deposit', 'withdrawal'])
        else:
            accounts = SavingsAccount.objects.filter(branch=user.branch)
            transactions = Transaction.objects.filter(
                transaction_type__in=['deposit', 'withdrawal'],
                branch=user.branch
            )
        
        # Calculate statistics
        stats = {
            'total_accounts': accounts.count(),
            'pending_approval': accounts.filter(status='pending').count(),
            'active': accounts.filter(status='active').count(),
            'suspended': accounts.filter(status='suspended').count(),
            'closed': accounts.filter(status='closed').count(),
            
            'total_balance': float(accounts.filter(status='active').aggregate(Sum('balance'))['balance__sum'] or 0),
            'average_balance': float(accounts.filter(status='active').aggregate(Avg('balance'))['balance__avg'] or 0),
            
            'total_deposits': float(transactions.filter(transaction_type='deposit', status='completed').aggregate(Sum('amount'))['amount__sum'] or 0),
            'total_withdrawals': float(transactions.filter(transaction_type='withdrawal', status='completed').aggregate(Sum('amount'))['amount__sum'] or 0),
            
            'accounts_by_type': {
                'daily': accounts.filter(account_type='daily').count(),
                'weekly': accounts.filter(account_type='weekly').count(),
                'monthly': accounts.filter(account_type='monthly').count(),
                'fixed': accounts.filter(account_type='fixed').count(),
            }
        }
        
        # return Response({
        #     'success': True,
        #     'statistics': stats
        # }, status=status.HTTP_200_OK)

        return Response(stats, status=status.HTTP_200_OK)


class TransactionHistoryView(generics.ListAPIView):
    """
    Get transaction history for a savings account
    Returns transactions array directly without pagination wrapper
    """
    permission_classes = [CanAccessSavingsAccount]
    
    def get_queryset(self):
        account_id = self.kwargs.get('account_id')
        return Transaction.objects.filter(
            savings_account__id=account_id
        ).order_by('-transaction_date')
    
    def list(self, request, *args, **kwargs):
        # Check if user can access the account
        try:
            account = SavingsAccount.objects.get(id=self.kwargs.get('account_id'))
            if not CanAccessSavingsAccount().has_object_permission(request, self, account):
                return Response({
                    'success': False,
                    'message': 'You do not have permission to view this transaction history.'
                }, status=status.HTTP_403_FORBIDDEN)
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Savings account not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # Build transactions list (no pagination)
        transactions = [{
            'id': str(t.id),
            'transaction_ref': t.transaction_ref,
            'transaction_type': t.transaction_type,
            'type': t.get_transaction_type_display(),
            'amount': float(t.amount),
            'balance_before': float(t.balance_before) if t.balance_before else None,
            'balance_after': float(t.balance_after) if t.balance_after else None,
            'status': t.get_status_display(),
            'date': str(t.transaction_date),  # Convert to string for JSON serialization
            'payment_method': None,  # Add this field if it exists in your Transaction model
            'processed_by': t.processed_by.get_full_name() if t.processed_by else None,
            'description': t.description,
            'notes': t.notes
        } for t in queryset]
        
        # Return transactions array directly (apiCall will wrap in {success: true, data: [...]})
        return Response(transactions, status=status.HTTP_200_OK)


class PendingTransactionsListView(APIView):
    """
    List all pending transactions that require approval
    Only accessible by manager, director, and admin
    """
    permission_classes = [IsManagerOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Build queryset based on user role
        queryset = Transaction.objects.filter(
            status='pending',
            transaction_type__in=['deposit', 'withdrawal']
        ).select_related('client', 'savings_account', 'branch', 'processed_by')
        
        # Branch managers can only see transactions from their branch
        if user.user_role == 'manager':
            queryset = queryset.filter(branch=user.branch)
        
        # Filter by transaction type if specified
        transaction_type = request.query_params.get('type')
        if transaction_type in ['deposit', 'withdrawal']:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by branch if specified (for directors/admins)
        branch_id = request.query_params.get('branch')
        if branch_id and user.user_role in ['director', 'admin']:
            queryset = queryset.filter(branch_id=branch_id)
        
        queryset = queryset.order_by('-created_at')
        
        transactions = [{
            'id': str(t.id),
            'transaction_ref': t.transaction_ref,
            'transaction_type': t.transaction_type,
            'type_display': t.get_transaction_type_display(),
            'amount': float(t.amount),
            'client_id': str(t.client.id),
            'client_name': t.client.get_full_name(),
            'client_email': t.client.email,
            'savings_account_id': str(t.savings_account.id) if t.savings_account else None,
            'account_number': t.savings_account.account_number if t.savings_account else None,
            'account_balance': float(t.savings_account.balance) if t.savings_account else None,
            'branch_id': str(t.branch.id),
            'branch_name': t.branch.name,
            'requested_by': t.processed_by.get_full_name() if t.processed_by else None,
            'requested_by_id': str(t.processed_by.id) if t.processed_by else None,
            'description': t.description,
            'notes': t.notes,
            'status': t.status,
            'created_at': t.created_at.isoformat(),
        } for t in queryset]
        
        # Get counts for dashboard
        counts = {
            'total_pending': queryset.count(),
            'pending_deposits': queryset.filter(transaction_type='deposit').count(),
            'pending_withdrawals': queryset.filter(transaction_type='withdrawal').count(),
        }
        
        return Response({
            'success': True,
            'transactions': transactions,
            'counts': counts
        }, status=status.HTTP_200_OK)


class TransactionApprovalView(APIView):
    """
    Approve or reject a pending transaction
    Only accessible by manager, director, and admin
    """
    permission_classes = [IsManagerOrAbove]
    
    def post(self, request, transaction_id):
        try:
            transaction = Transaction.objects.select_related(
                'savings_account', 'client', 'processed_by', 'branch'
            ).get(id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Transaction not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if transaction is pending
        if transaction.status != 'pending':
            return Response({
                'success': False,
                'message': f'Transaction is not pending. Current status: {transaction.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Branch managers can only approve transactions from their branch
        user = request.user
        if user.user_role == 'manager' and transaction.branch != user.branch:
            return Response({
                'success': False,
                'message': 'You can only approve transactions from your branch.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Prevent approving your own transactions (optional security measure)
        if transaction.processed_by and transaction.processed_by.id == user.id:
            # Allow directors and admins to approve their own transactions
            if user.user_role not in ['director', 'admin']:
                return Response({
                    'success': False,
                    'message': 'You cannot approve your own transaction requests.'
                }, status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action')  # 'approve' or 'reject'
        
        if action not in ['approve', 'reject']:
            return Response({
                'success': False,
                'message': 'Invalid action. Must be "approve" or "reject".'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if action == 'approve':
            return self._approve_transaction(transaction, user)
        else:
            rejection_reason = request.data.get('rejection_reason', '')
            if not rejection_reason:
                return Response({
                    'success': False,
                    'message': 'Rejection reason is required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            return self._reject_transaction(transaction, user, rejection_reason)
    
    def _approve_transaction(self, transaction, approver):
        """Process transaction approval"""
        account = transaction.savings_account
        
        if not account:
            return Response({
                'success': False,
                'message': 'Transaction has no associated savings account.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For withdrawals, verify sufficient balance
        if transaction.transaction_type == 'withdrawal':
            # Check for other pending withdrawals
            pending_withdrawals = Transaction.objects.filter(
                savings_account=account,
                transaction_type='withdrawal',
                status='pending'
            ).exclude(id=transaction.id).aggregate(total=models.Sum('amount'))['total'] or 0
            
            available_balance = account.balance - pending_withdrawals
            if transaction.amount > available_balance:
                return Response({
                    'success': False,
                    'message': f'Insufficient balance. Available: ₦{available_balance:,.2f}, Requested: ₦{transaction.amount:,.2f}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update balance
        balance_before = account.balance
        if transaction.transaction_type == 'deposit':
            account.balance += transaction.amount
        elif transaction.transaction_type == 'withdrawal':
            account.balance -= transaction.amount
        
        account.save()
        
        # Update transaction
        transaction.status = 'completed'
        transaction.approved_by = approver
        transaction.approved_at = timezone.now()
        transaction.balance_before = balance_before
        transaction.balance_after = account.balance
        transaction.save()
        
        # Notify the staff who requested the transaction
        if transaction.processed_by:
            Notification.objects.create(
                user=transaction.processed_by,
                notification_type='transaction_approved',
                title=f'{transaction.get_transaction_type_display()} Approved',
                message=f'Your {transaction.transaction_type} request of ₦{transaction.amount:,.2f} for {transaction.client.get_full_name()} has been approved by {approver.get_full_name()}.',
                related_savings=account
            )
        
        # Notify the account creator (client representative)
        if account.created_by and account.created_by != transaction.processed_by:
            Notification.objects.create(
                user=account.created_by,
                notification_type='deposit_made' if transaction.transaction_type == 'deposit' else 'withdrawal_made',
                title=f'{transaction.get_transaction_type_display()} Completed',
                message=f'{transaction.get_transaction_type_display()} of ₦{transaction.amount:,.2f} has been processed for account {account.account_number}. New balance: ₦{account.balance:,.2f}.',
                related_savings=account
            )
        
        return Response({
            'success': True,
            'message': f'{transaction.get_transaction_type_display()} approved successfully.',
            'transaction': {
                'id': str(transaction.id),
                'transaction_ref': transaction.transaction_ref,
                'amount': float(transaction.amount),
                'balance_before': float(balance_before),
                'balance_after': float(account.balance),
                'status': 'completed',
                'approved_by': approver.get_full_name(),
                'approved_at': transaction.approved_at.isoformat()
            }
        }, status=status.HTTP_200_OK)
    
    def _reject_transaction(self, transaction, rejector, reason):
        """Process transaction rejection"""
        # Update transaction
        transaction.status = 'rejected'
        transaction.approved_by = rejector
        transaction.approved_at = timezone.now()
        transaction.rejection_reason = reason
        transaction.save()
        
        # Notify the staff who requested the transaction
        if transaction.processed_by:
            Notification.objects.create(
                user=transaction.processed_by,
                notification_type='transaction_rejected',
                title=f'{transaction.get_transaction_type_display()} Rejected',
                message=f'Your {transaction.transaction_type} request of ₦{transaction.amount:,.2f} for {transaction.client.get_full_name()} has been rejected by {rejector.get_full_name()}. Reason: {reason}',
                related_savings=transaction.savings_account
            )
        
        return Response({
            'success': True,
            'message': f'{transaction.get_transaction_type_display()} rejected.',
            'transaction': {
                'id': str(transaction.id),
                'transaction_ref': transaction.transaction_ref,
                'amount': float(transaction.amount),
                'status': 'rejected',
                'rejected_by': rejector.get_full_name(),
                'rejection_reason': reason
            }
        }, status=status.HTTP_200_OK)


class TransactionDetailView(APIView):
    """
    Get details of a specific transaction
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request, transaction_id):
        try:
            transaction = Transaction.objects.select_related(
                'savings_account', 'client', 'processed_by', 'approved_by', 'branch'
            ).get(id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Transaction not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission for branch managers
        user = request.user
        if user.user_role == 'manager' and transaction.branch != user.branch:
            return Response({
                'success': False,
                'message': 'You can only view transactions from your branch.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = {
            'id': str(transaction.id),
            'transaction_ref': transaction.transaction_ref,
            'transaction_type': transaction.transaction_type,
            'type_display': transaction.get_transaction_type_display(),
            'amount': float(transaction.amount),
            'status': transaction.status,
            'status_display': transaction.get_status_display(),
            'client': {
                'id': str(transaction.client.id),
                'name': transaction.client.get_full_name(),
                'email': transaction.client.email,
            },
            'savings_account': {
                'id': str(transaction.savings_account.id),
                'account_number': transaction.savings_account.account_number,
                'balance': float(transaction.savings_account.balance),
            } if transaction.savings_account else None,
            'branch': {
                'id': str(transaction.branch.id),
                'name': transaction.branch.name,
            },
            'balance_before': float(transaction.balance_before) if transaction.balance_before else None,
            'balance_after': float(transaction.balance_after) if transaction.balance_after else None,
            'description': transaction.description,
            'notes': transaction.notes,
            'processed_by': {
                'id': str(transaction.processed_by.id),
                'name': transaction.processed_by.get_full_name(),
            } if transaction.processed_by else None,
            'approved_by': {
                'id': str(transaction.approved_by.id),
                'name': transaction.approved_by.get_full_name(),
            } if transaction.approved_by else None,
            'approved_at': transaction.approved_at.isoformat() if transaction.approved_at else None,
            'rejection_reason': transaction.rejection_reason,
            'created_at': transaction.created_at.isoformat(),
            'transaction_date': transaction.transaction_date.isoformat(),
        }
        
        return Response({
            'success': True,
            'transaction': data
        }, status=status.HTTP_200_OK)