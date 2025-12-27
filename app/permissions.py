"""
Custom Permission Classes for Role-Based Access Control
Implements fine-grained permissions for microfinance operations
Clean version without duplicates
"""

from rest_framework.permissions import BasePermission


class IsAuthenticated(BasePermission):
    """Allow access only to authenticated users"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdmin(BasePermission):
    """Allow access only to admin users"""
    message = "Only administrators can perform this action."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_role == 'admin'
        )


class IsDirectorOrAbove(BasePermission):
    """Allow access to directors and admins"""
    message = "Only directors and administrators can perform this action."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_role in ['director', 'admin']
        )


class IsManagerOrAbove(BasePermission):
    """Allow access to managers, directors, and admins"""
    message = "Only managers and above can perform this action."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_role in ['manager', 'director', 'admin']
        )


class IsStaffOrAbove(BasePermission):
    """Allow access to staff and above (excludes clients)"""
    message = "Only staff members can perform this action."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_role in ['staff', 'manager', 'director', 'admin']
        )


class IsClient(BasePermission):
    """Allow access only to client users"""
    message = "Only clients can perform this action."
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.user_role == 'client'
        )


class CanApproveUsers(BasePermission):
    """Only admins can approve user registrations"""
    message = "Only administrators can approve user registrations."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role == 'admin'


class CanApproveSavingsAccount(BasePermission):
    """Managers and above can approve savings accounts"""
    message = "Only managers and above can approve savings accounts."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['manager', 'director', 'admin']


class CanApproveLoan(BasePermission):
    """Managers and above can approve loans"""
    message = "Only managers, directors, and admins can approve loans."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['manager', 'director', 'admin']


class CanDisburseLoan(BasePermission):
    """Managers and above can disburse loans"""
    message = "Only managers, directors, and admins can disburse loans."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['manager', 'director', 'admin']


class CanManageBranch(BasePermission):
    """
    Check if user can manage a specific branch
    - Admin/Director: Can manage all branches
    - Manager: Can manage only their assigned branch
    """
    message = "You do not have permission to manage this branch."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['manager', 'director', 'admin']
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin and Director can manage all branches
        if user.user_role in ['director', 'admin']:
            return True
        
        # Manager can only manage their own branch
        if user.user_role == 'manager':
            return obj == user.branch
        
        return False


class CanAccessClient(BasePermission):
    """
    Check if user can access a specific client
    - Admin/Director: Can access all clients
    - Manager/Staff: Can access clients in their branch
    """
    message = "You do not have permission to access this client."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['staff', 'manager', 'director', 'admin']
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Get the client user object
        if hasattr(obj, 'user'):
            client_user = obj.user
        else:
            client_user = obj
        
        # Admin and Director can access all clients
        if user.user_role in ['director', 'admin']:
            return True
        
        # Manager and Staff can access clients in their branch
        if user.user_role in ['manager', 'staff']:
            return client_user.branch == user.branch
        
        return False


class CanAccessLoan(BasePermission):
    """
    Permission: User can access loan if:
    - Admin/Director: All loans
    - Manager/Staff: Loans in their branch
    """
    message = "You do not have permission to access this loan."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.user_role in ['staff', 'manager', 'director', 'admin']
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and Director can access all loans
        if request.user.user_role in ['admin', 'director']:
            return True
        
        # Manager and Staff can only access loans in their branch
        if request.user.user_role in ['manager', 'staff']:
            return obj.branch == request.user.branch
        
        return False


class CanAccessSavingsAccount(BasePermission):
    """
    Check if user can access a specific savings account
    Similar logic to CanAccessLoan
    """
    message = "You do not have permission to access this savings account."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admin and Director can access all accounts
        if user.user_role in ['director', 'admin']:
            return True
        
        # Manager and Staff can access accounts in their branch
        if user.user_role in ['manager', 'staff']:
            return obj.branch == user.branch
        
        # Client can only access their own accounts
        if user.user_role == 'client':
            return obj.client == user
        
        return False


class IsOwnerOrStaff(BasePermission):
    """
    Allow access to object owner or staff members
    Useful for client-specific data
    """
    message = "You do not have permission to access this resource."
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Staff and above can access
        if user.user_role in ['staff', 'manager', 'director', 'admin']:
            return True
        
        # Owner can access
        if hasattr(obj, 'user'):
            return obj.user == user
        if hasattr(obj, 'client'):
            return obj.client == user
        
        return False
    



    