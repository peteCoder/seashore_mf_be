"""
Complete URL Configuration
All API endpoints for the microfinance system
"""

from django.urls import path

from .auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    CustomTokenRefreshView,
    VerifyTokenView,
    CurrentUserView,
    PasswordChangeView,
    ClientPasswordSetView,
    ClientPasswordResetRequestView,
)
from .user_management_views import (
    UserListView,
    UserDetailView,
    UserApprovalView,
    UserActivationView,
    ClientListView,
    StaffListView,
    StaffUpdateView,
    StaffCreateView,
    StaffDetailView,
    StaffDeleteView,
    AssignClientToStaffView,

    ClientDetailView,
    ClientUpdateView,
    ClientDeleteView,

    # Guarantor and Next of Kin views
    GuarantorListCreateView,
    GuarantorDetailView,
    NextOfKinView,
)
from .loan_views import (
    LoanApplicationView,
    LoanListView,
    LoanDetailView,
    LoanApprovalView,
    LoanDisbursementView,
    LoanRepaymentView,
    LoanRepaymentScheduleView,
    LoanStatisticsView,
    LoanCalculationPreviewView,
    LoanTransactionsView,
)
from .savings_views import (
    SavingsAccountCreateView,
    SavingsAccountListView,
    SavingsAccountDetailView,
    SavingsAccountApprovalView,
    DepositView,
    WithdrawalView,
    SavingsStatisticsView,
    SavingsAccountStatusUpdateView,
    TransactionHistoryView,
    PendingTransactionsListView,
    TransactionApprovalView,
    TransactionDetailView,
)
from .dashboard_views import (
    DashboardOverviewView,
    LoanRepaymentChartView,
    SavingsActivityChartView,
    AccountDistributionChartView,
    ClientGrowthChartView,
)
from .notification_views import (
    NotificationListView,
    UnreadNotificationCountView,
    MarkNotificationAsReadView,
    MarkAllNotificationsAsReadView,
    DeleteNotificationView,
    DeleteAllNotificationsView,
)
from .views import (
    BranchListView,
    BranchCreateView,
    BranchDetailView,
    ClientCreateView,
    ClientImageUploadView,
)

app_name = 'app'

urlpatterns = [
    
    # ============================================
    # AUTHENTICATION ENDPOINTS
    # ============================================
    
    # Public authentication endpoints
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', VerifyTokenView.as_view(), name='token_verify'),
    
    # Authenticated user endpoints
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('auth/password/change/', PasswordChangeView.as_view(), name='password_change'),
    
    # Client password management (public)
    path('auth/client/password/set/', ClientPasswordSetView.as_view(), name='client_password_set'),
    path('auth/client/password/reset/request/', ClientPasswordResetRequestView.as_view(), name='client_password_reset_request'),
    
    # ============================================
    # BRANCH MANAGEMENT ENDPOINTS
    # ============================================
    
    path('branches/', BranchListView.as_view(), name='branch_list'),
    path('branches/create/', BranchCreateView.as_view(), name='branch_create'),
    path('branches/<uuid:id>/', BranchDetailView.as_view(), name='branch_detail'),
    
    # ============================================
    # USER MANAGEMENT ENDPOINTS
    # ============================================
    
    # General user management
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<uuid:id>/', UserDetailView.as_view(), name='user_detail'),
    path('users/<uuid:user_id>/approve/', UserApprovalView.as_view(), name='user_approval'),
    path('users/<uuid:user_id>/activate/', UserActivationView.as_view(), name='user_activation'),
    
    # Client management
    path('clients/', ClientListView.as_view(), name='client_list'),
    path('clients/create/', ClientCreateView.as_view(), name='client_create'),
    path('clients/<uuid:id>/', ClientDetailView.as_view(), name='client_detail'),
    path('clients/<uuid:id>/update/', ClientUpdateView.as_view(), name='client_update'),
    path('clients/<uuid:id>/delete/', ClientDeleteView.as_view(), name='client_delete'),
    path('clients/<uuid:client_id>/upload-images/', ClientImageUploadView.as_view(), name='client_upload_images'),
    path('clients/<uuid:client_id>/assign-staff/', AssignClientToStaffView.as_view(), name='assign_client_to_staff'),
    
    # Guarantor management (using combined views from user_management_views)
    path('clients/<uuid:client_id>/guarantors/', GuarantorListCreateView.as_view(), name='guarantor_list_create'),
    path('clients/<uuid:client_id>/guarantors/<uuid:guarantor_id>/', GuarantorDetailView.as_view(), name='guarantor_detail'),
    
    # Next of Kin management (using combined view from user_management_views)
    path('clients/<uuid:client_id>/next-of-kin/', NextOfKinView.as_view(), name='next_of_kin'),
    
    # Staff management
    path('staff/', StaffListView.as_view(), name='staff_list'),
    path('staff/create/', StaffCreateView.as_view(), name='staff_create'),
    path('staff/<uuid:staff_id>/update/', StaffUpdateView.as_view(), name='staff_update'),
    path('staff/<uuid:id>/', StaffDetailView.as_view(), name='staff_detail'),
    path('staff/<uuid:id>/delete/', StaffDeleteView.as_view(), name='staff_delete'),
    
    # ============================================
    # LOAN MANAGEMENT ENDPOINTS
    # ============================================
    
    # Loan application and listing
    path('loans/', LoanListView.as_view(), name='loan_list'),
    path('loans/apply/', LoanApplicationView.as_view(), name='loan_apply'),
    path('loans/statistics/', LoanStatisticsView.as_view(), name='loan_statistics'),
    
    # Loan details and actions
    path('loans/<uuid:loan_id>/transactions/', LoanTransactionsView.as_view(), name='loan_transactions'),
    path('loans/<uuid:id>/', LoanDetailView.as_view(), name='loan_detail'),
    path('loans/<uuid:loan_id>/approve/', LoanApprovalView.as_view(), name='loan_approval'),
    path('loans/<uuid:loan_id>/disburse/', LoanDisbursementView.as_view(), name='loan_disbursement'),
    path('loans/<uuid:loan_id>/repay/', LoanRepaymentView.as_view(), name='loan_repayment'),
    path('loans/<uuid:loan_id>/schedule/', LoanRepaymentScheduleView.as_view(), name='loan_schedule'),
    path('loans/calculate/', LoanCalculationPreviewView.as_view(), name='loan_calculate'),
    
    # ============================================
    # SAVINGS ACCOUNT ENDPOINTS
    # ============================================
    
    # Savings account management
    path('savings/', SavingsAccountListView.as_view(), name='savings_list'),
    path('savings/create/', SavingsAccountCreateView.as_view(), name='savings_create'),
    path('savings/<uuid:account_id>/status/', SavingsAccountStatusUpdateView.as_view(), name='savings_status_update'),
    path('savings/statistics/', SavingsStatisticsView.as_view(), name='savings_statistics'),
    
    # Savings account details and actions
    path('savings/<uuid:id>/', SavingsAccountDetailView.as_view(), name='savings_detail'),
    path('savings/<uuid:account_id>/approve/', SavingsAccountApprovalView.as_view(), name='savings_approval'),
    path('savings/<uuid:account_id>/deposit/', DepositView.as_view(), name='savings_deposit'),
    path('savings/<uuid:account_id>/withdraw/', WithdrawalView.as_view(), name='savings_withdrawal'),
    path('savings/<uuid:account_id>/transactions/', TransactionHistoryView.as_view(), name='savings_transactions'),
    
    # Transaction approval workflow
    path('transactions/pending/', PendingTransactionsListView.as_view(), name='pending_transactions'),
    path('transactions/<uuid:transaction_id>/', TransactionDetailView.as_view(), name='transaction_detail'),
    path('transactions/<uuid:transaction_id>/approve/', TransactionApprovalView.as_view(), name='transaction_approval'),
    
    # ============================================
    # DASHBOARD ENDPOINTS
    # ============================================
    
    # Main dashboard
    path('dashboard/', DashboardOverviewView.as_view(), name='dashboard_overview'),
    
    # Chart data endpoints
    path('dashboard/charts/loan-repayment/', LoanRepaymentChartView.as_view(), name='chart_loan_repayment'),
    path('dashboard/charts/savings-activity/', SavingsActivityChartView.as_view(), name='chart_savings_activity'),
    path('dashboard/charts/account-distribution/', AccountDistributionChartView.as_view(), name='chart_account_distribution'),
    path('dashboard/charts/client-growth/', ClientGrowthChartView.as_view(), name='chart_client_growth'),
    
    # ============================================
    # NOTIFICATION ENDPOINTS
    # ============================================
    
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/unread-count/', UnreadNotificationCountView.as_view(), name='notification_unread_count'),
    path('notifications/<uuid:notification_id>/read/', MarkNotificationAsReadView.as_view(), name='notification_mark_read'),
    path('notifications/mark-all-read/', MarkAllNotificationsAsReadView.as_view(), name='notification_mark_all_read'),
    path('notifications/<uuid:notification_id>/delete/', DeleteNotificationView.as_view(), name='notification_delete'),
    path('notifications/delete-all/', DeleteAllNotificationsView.as_view(), name='notification_delete_all'),
]