"""
Loan Views
Complete CRUD operations and workflows for loan management
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from datetime import timedelta
from decimal import Decimal


class LoanApplicationView(APIView):
    """
    Submit new loan application
    Staff and above can create loans for clients
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        from .loan_serializers import LoanApplicationSerializer, LoanDetailSerializer
        from .models import Loan, Notification, User
        
        # Check if user is staff or above
        if request.user.user_role not in ['staff', 'manager', 'director', 'admin']:
            return Response({
                'success': False,
                'message': 'Only staff and above can create loan applications.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LoanApplicationSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        loan = serializer.save()
        
        # Create notifications for managers
        managers = User.objects.filter(
            user_role__in=['manager', 'director', 'admin'],
            branch=loan.branch,
            is_active=True
        )
        
        for manager in managers:
            Notification.objects.create(
                user=manager,
                notification_type='loan_applied',
                title='New Loan Application',
                message=f'{loan.client.get_full_name()} has applied for a loan of ₦{loan.principal_amount:,.2f}.',
                is_urgent=True,
                related_loan=loan,
                related_client=loan.client
            )
        
        return Response({
            'success': True,
            'message': 'Loan application submitted successfully',
            'data': LoanDetailSerializer(loan).data
        }, status=status.HTTP_201_CREATED)


class LoanCalculationPreviewView(APIView):
    """
    Calculate loan details without creating a loan.
    Used for live preview in frontend.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        from .loan_serializers import LoanCalculationPreviewSerializer
        
        serializer = LoanCalculationPreviewSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # The validated_data contains the calculation result
        calc_result = serializer.validated_data
        
        # Convert Decimal to float for JSON
        calculation = {
            'principal_amount': float(calc_result['principal_amount']),
            'monthly_interest_rate': float(calc_result['monthly_interest_rate'] * 100),  # As percentage
            'annual_interest_rate': float(calc_result['annual_interest_rate']),
            'duration_value': calc_result['duration_value'],
            'duration_months': float(calc_result['duration_months']),
            'repayment_frequency': calc_result['repayment_frequency'],
            'total_interest': float(calc_result['total_interest']),
            'total_repayment': float(calc_result['total_repayment']),
            'installment_amount': float(calc_result['installment_amount']),
            'number_of_installments': calc_result['number_of_installments'],
        }
        
        return Response({
            'success': True,
            'data': {
                'calculation': calculation
            }
        }, status=status.HTTP_200_OK)


class LoanListView(APIView):
    """
    List all loans with filtering
    Admin/Director: See all loans
    Manager/Staff: See loans in their branch
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from .models import Loan
        from .loan_serializers import LoanListSerializer
        
        user = request.user
        
        # Base queryset based on role
        if user.user_role in ['admin', 'director']:
            queryset = Loan.objects.all()
        else:
            queryset = Loan.objects.filter(branch=user.branch)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        client_id = request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client__id=client_id)
        
        branch_id = request.query_params.get('branch_id')
        if branch_id and user.user_role in ['admin', 'director']:
            queryset = queryset.filter(branch__id=branch_id)
        
        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(loan_number__icontains=search) |
                Q(client__first_name__icontains=search) |
                Q(client__last_name__icontains=search) |
                Q(client__email__icontains=search)
            )
        
        # Order by most recent
        queryset = queryset.select_related('client', 'branch', 'created_by').order_by('-application_date')
        
        # Serialize
        serializer = LoanListSerializer(queryset, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class LoanDetailView(APIView):
    """Get detailed loan information"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, id):
        from .models import Loan
        from .loan_serializers import LoanDetailSerializer
        
        try:
            loan = Loan.objects.select_related('client', 'branch', 'created_by', 'approved_by', 'disbursed_by').get(id=id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.user_role not in ['admin', 'director']:
            if loan.branch != user.branch:
                return Response({
                    'success': False,
                    'message': 'You do not have permission to view this loan'
                }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = LoanDetailSerializer(loan)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class LoanApprovalView(APIView):
    """
    Approve or reject loan application
    Only managers, directors, and admins can approve
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, loan_id):
        from .models import Loan, Notification
        from .loan_serializers import LoanApprovalSerializer, LoanDetailSerializer
        
        # Check permission
        if request.user.user_role not in ['manager', 'director', 'admin']:
            return Response({
                'success': False,
                'message': 'Only managers, directors, and admins can approve/reject loans'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check branch access
        if request.user.user_role not in ['admin', 'director']:
            if loan.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only approve loans in your branch'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate loan status
        if loan.status != 'pending_approval':
            return Response({
                'success': False,
                'message': f'Cannot process loan. Current status: {loan.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LoanApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        
        if action == 'approve':
            success, message = loan.approve(approved_by=request.user)
            
            if not success:
                return Response({
                    'success': False,
                    'message': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Notify staff who created the loan
            if loan.created_by:
                Notification.objects.create(
                    user=loan.created_by,
                    notification_type='loan_approved',
                    title='Loan Approved',
                    message=f'Loan {loan.loan_number} for {loan.client.get_full_name()} has been approved',
                    related_loan=loan
                )
            
            response_message = 'Loan approved successfully. Ready for disbursement.'
            
        else:  # reject
            success, message = loan.reject(
                rejection_reason=serializer.validated_data.get('rejection_reason', '')
            )
            
            if not success:
                return Response({
                    'success': False,
                    'message': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Notify staff who created the loan
            if loan.created_by:
                Notification.objects.create(
                    user=loan.created_by,
                    notification_type='loan_rejected',
                    title='Loan Rejected',
                    message=f'Loan {loan.loan_number} for {loan.client.get_full_name()} has been rejected',
                    related_loan=loan
                )
            
            response_message = 'Loan rejected'
        
        return Response({
            'success': True,
            'message': response_message,
            'data': LoanDetailSerializer(loan).data
        }, status=status.HTTP_200_OK)



class LoanTransactionsView(APIView):
    """
    Get all transactions for a specific loan
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, loan_id):
        from .models import Loan, Transaction
        
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.user_role not in ['admin', 'director']:
            if loan.branch != user.branch:
                return Response({
                    'success': False,
                    'message': 'You do not have permission to view these transactions'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get loan-related transactions
        transactions = Transaction.objects.filter(
            loan=loan,
            status='completed'
        ).select_related('processed_by').order_by('-transaction_date')
        
        # Format transaction data
        transactions_data = []
        for txn in transactions:
            transactions_data.append({
                'id': str(txn.id),
                'transaction_ref': txn.transaction_ref,
                'transaction_type': txn.transaction_type,
                'amount': float(txn.amount),
                'date': txn.transaction_date.isoformat(),
                'payment_method': txn.description.split(':')[-1].strip() if ':' in txn.description else 'N/A',
                'reference': txn.transaction_ref,
                'notes': txn.notes,
                'recorded_by': txn.processed_by.get_full_name() if txn.processed_by else 'System',
                'balance_before': float(txn.balance_before) if txn.balance_before else None,
                'balance_after': float(txn.balance_after) if txn.balance_after else None,
            })
        
        return Response({
            'success': True,
            'data': transactions_data
        }, status=status.HTTP_200_OK)


class LoanDisbursementView(APIView):
    """
    Disburse approved loan
    Managers and above can disburse loans
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, loan_id):
        from .models import Loan, Transaction, Notification
        from .loan_serializers import LoanDisbursementSerializer, LoanDetailSerializer
        
        # Check permission
        if request.user.user_role not in ['manager', 'director', 'admin']:
            return Response({
                'success': False,
                'message': 'Only managers, directors, and admins can disburse loans'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check branch access
        if request.user.user_role not in ['admin', 'director']:
            if loan.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only disburse loans in your branch'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate loan status
        if loan.status != 'approved':
            return Response({
                'success': False,
                'message': f'Only approved loans can be disbursed. Current status: {loan.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LoanDisbursementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Disburse loan
        success, message = loan.disburse(disbursed_by=request.user)
        
        if not success:
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update disbursement details
        loan.disbursement_method = serializer.validated_data.get('disbursement_method')
        loan.bank_name = serializer.validated_data.get('bank_name', '')
        loan.bank_account_number = serializer.validated_data.get('account_number', '')
        loan.bank_account_name = serializer.validated_data.get('account_name', '')
        loan.disbursement_reference = serializer.validated_data.get('transaction_reference', '')
        loan.disbursement_notes = serializer.validated_data.get('disbursement_notes', '')
        loan.save()
        
        # Create transaction record
        transaction_ref = f"DISB{timezone.now().strftime('%Y%m%d%H%M%S')}{str(loan.id)[:6]}"
        Transaction.objects.create(
            transaction_ref=transaction_ref,
            transaction_type='loan_disbursement',
            amount=loan.principal_amount,
            client=loan.client,
            loan=loan,
            branch=loan.branch,
            processed_by=request.user,
            description=f'Loan disbursement: {loan.loan_number}',
            notes=serializer.validated_data.get('disbursement_notes', ''),
            status='completed'
        )
        
        # Notify loan officer
        if loan.created_by:
            Notification.objects.create(
                user=loan.created_by,
                notification_type='loan_disbursed',
                title='Loan Disbursed',
                message=f'Loan {loan.loan_number} for {loan.client.get_full_name()} has been disbursed',
                related_loan=loan
            )
        
        return Response({
            'success': True,
            'message': 'Loan disbursed successfully',
            'data': LoanDetailSerializer(loan).data
        }, status=status.HTTP_200_OK)


class LoanRepaymentView(APIView):
    """
    Record loan repayment
    Staff and above can record repayments
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, loan_id):
        from .models import Loan, Transaction, Notification
        from .loan_serializers import LoanRepaymentSerializer, LoanDetailSerializer
        
        # Check permission
        if request.user.user_role not in ['staff', 'manager', 'director', 'admin']:
            return Response({
                'success': False,
                'message': 'Only staff and above can record loan repayments'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check branch access
        if request.user.user_role not in ['admin', 'director']:
            if loan.branch != request.user.branch:
                return Response({
                    'success': False,
                    'message': 'You can only record repayments for loans in your branch'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Validate loan status
        if loan.status not in ['active', 'overdue']:
            return Response({
                'success': False,
                'message': f'Cannot record repayment. Loan status: {loan.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LoanRepaymentSerializer(data=request.data, context={'loan': loan})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        amount = serializer.validated_data['amount']
        
        try:
            # Record repayment
            remaining_balance = loan.record_repayment(amount)
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create transaction record
        transaction_ref = f"RPMT{timezone.now().strftime('%Y%m%d%H%M%S')}{str(loan.id)[:6]}"
        Transaction.objects.create(
            transaction_ref=transaction_ref,
            transaction_type='loan_repayment',
            amount=amount,
            client=loan.client,
            loan=loan,
            branch=loan.branch,
            processed_by=request.user,
            description=f'Loan repayment: {loan.loan_number}',
            notes=serializer.validated_data.get('payment_notes', ''),
            status='completed'
        )
        
        # Notification message
        if remaining_balance <= 0:
            notification_message = f'Loan {loan.loan_number} has been fully repaid!'
            notification_type = 'loan_completed'
        else:
            notification_message = f'Repayment of ₦{amount:,.2f} recorded for loan {loan.loan_number}. Balance: ₦{remaining_balance:,.2f}'
            notification_type = 'loan_repayment'
        
        # Notify loan officer
        if loan.created_by:
            Notification.objects.create(
                user=loan.created_by,
                notification_type=notification_type,
                title='Loan Repayment Recorded',
                message=notification_message,
                related_loan=loan
            )
        
        return Response({
            'success': True,
            'message': 'Repayment recorded successfully',
            'data': {
                'remaining_balance': float(remaining_balance),
                'loan': LoanDetailSerializer(loan).data
            }
        }, status=status.HTTP_200_OK)


class LoanStatisticsView(APIView):
    """Get loan statistics for dashboard"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from .models import Loan
        
        user = request.user
        
        # Filter loans based on role
        if user.user_role in ['admin', 'director']:
            loans = Loan.objects.all()
        else:
            loans = Loan.objects.filter(branch=user.branch)
        
        # Calculate statistics
        stats = {
            'total_loans': loans.count(),
            'pending_approval': loans.filter(status='pending_approval').count(),
            'approved': loans.filter(status='approved').count(),
            'active': loans.filter(status='active').count(),
            'overdue': loans.filter(status='overdue').count(),
            'completed': loans.filter(status='completed').count(),
            'rejected': loans.filter(status='rejected').count(),
            
            'total_disbursed': float(
                loans.filter(status__in=['active', 'overdue', 'completed'])
                .aggregate(Sum('amount_disbursed'))['amount_disbursed__sum'] or 0
            ),
            'total_repayments': float(
                loans.filter(status__in=['active', 'overdue', 'completed'])
                .aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
            ),
            'total_outstanding': float(
                loans.filter(status__in=['active', 'overdue'])
                .aggregate(Sum('outstanding_balance'))['outstanding_balance__sum'] or 0
            ),
            
            'average_loan_amount': float(
                loans.aggregate(Avg('principal_amount'))['principal_amount__avg'] or 0
            ),
        }
        
        return Response({
            'success': True,
            'data': stats
        }, status=status.HTTP_200_OK)


class LoanRepaymentScheduleView(APIView):
    """Generate and view loan repayment schedule"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, loan_id):
        from .models import Loan
        from .loan_calculator import LoanCalculator
        
        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Loan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.user_role not in ['admin', 'director']:
            if loan.branch != user.branch:
                return Response({
                    'success': False,
                    'message': 'You do not have permission to view this schedule'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Generate schedule using calculator
        schedule = LoanCalculator.generate_repayment_schedule(
            principal_amount=loan.principal_amount,
            frequency=loan.repayment_frequency,
            duration_value=loan.duration_value,
            start_date=loan.disbursement_date or loan.application_date
        )
        
        return Response({
            'success': True,
            'data': schedule
        }, status=status.HTTP_200_OK)