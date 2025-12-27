"""
Dashboard Views - FIXED VERSION
Comprehensive statistics and chart data for dashboard
Matches frontend expectations exactly
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Sum, Count, F, Case, When, Value, IntegerField
from django.db.models.functions import TruncMonth, TruncDate
from datetime import timedelta
from decimal import Decimal

from .models import (
    User, ClientProfile, StaffProfile, Loan, SavingsAccount,
    Transaction, Notification, Branch
)
from .permissions import IsStaffOrAbove


class DashboardOverviewView(APIView):
    """
    Main dashboard overview with key metrics
    Different metrics based on user role
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Get data based on role
        if user.user_role in ['admin', 'director']:
            # Admin/Director see all data
            data = self._get_admin_dashboard_data()
        elif user.user_role == 'manager':
            # Manager sees branch data
            data = self._get_manager_dashboard_data(user.branch)
        else:  # staff
            # Staff sees assigned clients data
            data = self._get_staff_dashboard_data(user)
        
        # ✅ FIX: Return data in format frontend expects
        return Response({
            'success': True,
            'data': {
                'total_loans_disbursed': data['stats'].get('loans', {}).get('total_disbursed', 0),
                'total_repayments': data['stats'].get('loans', {}).get('total_repayments', 0),
                'total_savings_balance': data['stats'].get('savings', {}).get('total_balance', 0),
                'total_withdrawals': data['stats'].get('savings', {}).get('total_withdrawals', 0),
                'total_clients': data['stats'].get('clients', {}).get('total', 0),
                'total_staff': data['stats'].get('staff', {}).get('total', 0),
                'active_loans': data['stats'].get('loans', {}).get('active_count', 0),
                'pending_loan_applications': data['stats'].get('loans', {}).get('pending_approval', 0),
            },
            'dashboard': data  # Keep full data for debugging if needed
        }, status=status.HTTP_200_OK)
    
    def _get_admin_dashboard_data(self):
        """Get dashboard data for admin/director"""
        
        # Client statistics
        total_clients = User.objects.filter(user_role='client').count()
        active_clients = User.objects.filter(user_role='client', is_active=True, is_approved=True).count()
        restricted_clients = User.objects.filter(user_role='client', is_active=True, is_approved=False).count()
        deactivated_clients = User.objects.filter(user_role='client', is_active=False).count()
        
        # Staff statistics
        total_staff = User.objects.filter(user_role__in=['staff', 'manager', 'director']).count()
        active_staff = User.objects.filter(user_role__in=['staff', 'manager', 'director'], is_active=True).count()
        suspended_staff = User.objects.filter(user_role__in=['staff', 'manager', 'director'], is_active=False, is_approved=True).count()
        
        # Loan statistics
        total_loans_disbursed = Loan.objects.filter(
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_disbursed'))['amount_disbursed__sum'] or 0
        
        total_repayments = Loan.objects.filter(
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        
        active_loans_count = Loan.objects.filter(status__in=['active', 'overdue']).count()
        pending_loan_approvals = Loan.objects.filter(status='pending').count()
        overdue_loans_count = Loan.objects.filter(status='overdue').count()
        
        # Savings statistics
        total_savings_balance = SavingsAccount.objects.filter(
            status='active'
        ).aggregate(Sum('balance'))['balance__sum'] or 0
        
        total_deposits = Transaction.objects.filter(
            transaction_type='deposit',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_savings_accounts = SavingsAccount.objects.filter(status__in=['pending', 'active']).count()
        total_loan_accounts = Loan.objects.filter(status__in=['pending', 'approved', 'active', 'overdue']).count()
        
        return {
            'stats': {
                'clients': {
                    'total': total_clients,
                    'active': active_clients,
                    'restricted': restricted_clients,
                    'deactivated': deactivated_clients,
                },
                'staff': {
                    'total': total_staff,
                    'active': active_staff,
                    'suspended': suspended_staff,
                },
                'loans': {
                    'total_disbursed': float(total_loans_disbursed),
                    'total_repayments': float(total_repayments),
                    'active_count': active_loans_count,
                    'pending_approval': pending_loan_approvals,
                    'overdue': overdue_loans_count,
                },
                'savings': {
                    'total_balance': float(total_savings_balance),
                    'total_deposits': float(total_deposits),
                    'total_withdrawals': float(total_withdrawals),
                    'total_accounts': total_savings_accounts,
                },
                'accounts': {
                    'total_savings_accounts': total_savings_accounts,
                    'total_loan_accounts': total_loan_accounts,
                }
            },
            'role': 'admin'
        }
    
    def _get_manager_dashboard_data(self, branch):
        """Get dashboard data for manager (branch-specific)"""
        
        # Client statistics (branch)
        total_clients = User.objects.filter(user_role='client', branch=branch).count()
        active_clients = User.objects.filter(user_role='client', branch=branch, is_active=True, is_approved=True).count()
        restricted_clients = User.objects.filter(user_role='client', branch=branch, is_active=True, is_approved=False).count()
        deactivated_clients = User.objects.filter(user_role='client', branch=branch, is_active=False).count()
        
        # Loan statistics (branch)
        total_loans_disbursed = Loan.objects.filter(
            branch=branch,
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_disbursed'))['amount_disbursed__sum'] or 0
        
        total_repayments = Loan.objects.filter(
            branch=branch,
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        
        active_loans_count = Loan.objects.filter(branch=branch, status__in=['active', 'overdue']).count()
        pending_loan_approvals = Loan.objects.filter(branch=branch, status='pending').count()
        overdue_loans_count = Loan.objects.filter(branch=branch, status='overdue').count()
        
        # Savings statistics (branch)
        total_savings_balance = SavingsAccount.objects.filter(
            branch=branch,
            status='active'
        ).aggregate(Sum('balance'))['balance__sum'] or 0
        
        total_deposits = Transaction.objects.filter(
            branch=branch,
            transaction_type='deposit',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_withdrawals = Transaction.objects.filter(
            branch=branch,
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return {
            'stats': {
                'clients': {
                    'total': total_clients,
                    'active': active_clients,
                    'restricted': restricted_clients,
                    'deactivated': deactivated_clients,
                },
                'loans': {
                    'total_disbursed': float(total_loans_disbursed),
                    'total_repayments': float(total_repayments),
                    'active_count': active_loans_count,
                    'pending_approval': pending_loan_approvals,
                    'overdue': overdue_loans_count,
                },
                'savings': {
                    'total_balance': float(total_savings_balance),
                    'total_deposits': float(total_deposits),
                    'total_withdrawals': float(total_withdrawals),
                },
                'staff': {
                    'total': 0,  # Add this for consistency
                }
            },
            'role': 'manager',
            'branch': branch.name if branch else None
        }
    
    def _get_staff_dashboard_data(self, user):
        """Get dashboard data for staff (assigned clients only)"""
        
        # Get assigned clients
        assigned_clients = ClientProfile.objects.filter(assigned_staff=user)
        client_users = [cp.user for cp in assigned_clients]
        
        # Loan statistics (assigned clients)
        total_loans_disbursed = Loan.objects.filter(
            client__in=client_users,
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_disbursed'))['amount_disbursed__sum'] or 0
        
        total_repayments = Loan.objects.filter(
            client__in=client_users,
            status__in=['active', 'overdue', 'completed']
        ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        
        active_loans_count = Loan.objects.filter(client__in=client_users, status__in=['active', 'overdue']).count()
        overdue_loans_count = Loan.objects.filter(client__in=client_users, status='overdue').count()
        pending_loan_approvals = Loan.objects.filter(client__in=client_users, status='pending').count()
        
        outstanding_balance = Loan.objects.filter(
            client__in=client_users,
            status__in=['active', 'overdue']
        ).aggregate(Sum('outstanding_balance'))['outstanding_balance__sum'] or 0
        
        return {
            'stats': {
                'assigned_clients': len(client_users),
                'clients': {
                    'total': len(client_users),
                    'active': len(client_users),
                    'restricted': 0,
                    'deactivated': 0,
                },
                'loans': {
                    'total_disbursed': float(total_loans_disbursed),
                    'total_repayments': float(total_repayments),
                    'active_count': active_loans_count,
                    'overdue': overdue_loans_count,
                    'pending_approval': pending_loan_approvals,
                    'outstanding_balance': float(outstanding_balance),
                },
                'savings': {
                    'total_balance': 0,
                    'total_deposits': 0,
                    'total_withdrawals': 0,
                },
                'staff': {
                    'total': 0,
                }
            },
            'role': 'staff'
        }


class LoanRepaymentChartView(APIView):
    """
    Loan repayment chart data (Area chart)
    Shows monthly disbursements vs repayments
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Get loans based on role
        if user.user_role in ['admin', 'director']:
            loans = Loan.objects.all()
            transactions_filter = {}
        else:
            loans = Loan.objects.filter(branch=user.branch)
            transactions_filter = {'branch': user.branch}
        
        # Get data for last 12 months
        end_date = timezone.now().date()
        start_date = end_date.replace(month=1, day=1)  # Start of current year
        
        # Monthly disbursements
        disbursements = loans.filter(
            disbursement_date__gte=start_date,
            disbursement_date__lte=end_date
        ).annotate(
            month=TruncMonth('disbursement_date')
        ).values('month').annotate(
            total=Sum('amount_disbursed')
        ).order_by('month')
        
        # Monthly repayments
        repayments = Transaction.objects.filter(
            transaction_type='loan_repayment',
            status='completed',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            **transactions_filter
        ).annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        # Create chart data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        current_year = end_date.year
        
        monthly_data = []
        for i in range(12):
            # Get disbursement for this month
            disb = next((d['total'] for d in disbursements if d['month'].month == i+1), 0)
            repay = next((r['total'] for r in repayments if r['month'].month == i+1), 0)
            
            monthly_data.append({
                'month': months[i],
                'disbursed': float(disb or 0),
                'repayments': float(repay or 0)
            })
        
        # ✅ FIX: Return in format frontend expects
        return Response({
            'success': True,
            'data': {
                'monthly_data': monthly_data
            }
        }, status=status.HTTP_200_OK)


class SavingsActivityChartView(APIView):
    """
    Savings activity chart data (Bar chart)
    Shows monthly deposits vs withdrawals
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Get filter conditions based on role
        if user.user_role in ['admin', 'director']:
            branch_filter = {}
        else:
            branch_filter = {'branch': user.branch}
        
        # Get data for last 12 months
        end_date = timezone.now().date()
        start_date = end_date.replace(month=1, day=1)
        
        # Monthly deposits
        deposits = Transaction.objects.filter(
            transaction_type='deposit',
            status='completed',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            **branch_filter
        ).annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        # Monthly withdrawals
        withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            status='completed',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            **branch_filter
        ).annotate(
            month=TruncMonth('transaction_date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        # Create chart data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        monthly_data = []
        for i in range(12):
            dep = next((d['total'] for d in deposits if d['month'].month == i+1), 0)
            wit = next((w['total'] for w in withdrawals if w['month'].month == i+1), 0)
            
            monthly_data.append({
                'month': months[i],
                'deposits': float(dep or 0),
                'withdrawals': float(wit or 0)
            })
        
        # ✅ FIX: Return in format frontend expects
        return Response({
            'success': True,
            'data': {
                'monthly_data': monthly_data
            }
        }, status=status.HTTP_200_OK)


class AccountDistributionChartView(APIView):
    """
    Account distribution chart data (Pie chart)
    Shows distribution of Savings Only, Loan Only, Savings+Loans
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Get clients based on role
        if user.user_role in ['admin', 'director']:
            clients = User.objects.filter(user_role='client', is_approved=True)
        else:
            clients = User.objects.filter(user_role='client', branch=user.branch, is_approved=True)
        
        # Count clients by account types
        savings_only = 0
        loan_only = 0
        both = 0
        
        for client in clients:
            has_savings = SavingsAccount.objects.filter(client=client, status='active').exists()
            has_loan = Loan.objects.filter(client=client, status__in=['active', 'overdue']).exists()
            
            if has_savings and has_loan:
                both += 1
            elif has_savings:
                savings_only += 1
            elif has_loan:
                loan_only += 1
        
        # ✅ FIX: Return in format frontend expects (object, not array)
        return Response({
            'success': True,
            'data': {
                'savings_only': savings_only,
                'loan_only': loan_only,
                'both': both
            }
        }, status=status.HTTP_200_OK)


class ClientGrowthChartView(APIView):
    """
    Client growth chart data (Line chart)
    Shows monthly client acquisition (total and active)
    """
    permission_classes = [IsStaffOrAbove]
    
    def get(self, request):
        user = request.user
        
        # Get filter conditions based on role
        if user.user_role in ['admin', 'director']:
            branch_filter = {}
        else:
            branch_filter = {'branch': user.branch}
        
        # Get data for last 12 months
        end_date = timezone.now()
        start_date = end_date.replace(month=1, day=1)
        
        # Monthly client registrations
        registrations = User.objects.filter(
            user_role='client',
            created_at__gte=start_date,
            created_at__lte=end_date,
            **branch_filter
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Count('id'),
            active=Count(Case(When(is_active=True, is_approved=True, then=1), output_field=IntegerField()))
        ).order_by('month')
        
        # Create chart data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        cumulative_total = 0
        cumulative_active = 0
        
        monthly_data = []
        for i in range(12):
            reg = next((r for r in registrations if r['month'].month == i+1), {'total': 0, 'active': 0})
            
            cumulative_total += reg['total']
            cumulative_active += reg['active']
            
            monthly_data.append({
                'month': months[i],
                'total': cumulative_total,
                'active': cumulative_active
            })
        
        # ✅ FIX: Return in format frontend expects
        return Response({
            'success': True,
            'data': {
                'monthly_data': monthly_data
            }
        }, status=status.HTTP_200_OK)