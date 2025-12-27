from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import get_random_string
from .models import (
    User, ClientProfile, StaffProfile,
    Loan, SavingsAccount, Transaction, Notification
)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create profile based on user role"""
    if created:
        if instance.user_role == 'client':
            # Create client profile
            ClientProfile.objects.create(
                user=instance,
                level='bronze'  # Default level
            )
            # Set unusable password for clients
            if instance.has_usable_password():
                instance.set_unusable_password()
                instance.save(update_fields=['password'])


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save profile when user is saved"""
    if instance.user_role == 'client' and hasattr(instance, 'client_profile'):
        instance.client_profile.save()
    elif instance.user_role in ['staff', 'manager', 'director', 'admin'] and hasattr(instance, 'staff_profile'):
        instance.staff_profile.save()


@receiver(pre_save, sender=StaffProfile)
def generate_employee_id(sender, instance, **kwargs):
    """Auto-generate employee ID if not provided"""
    if not instance.employee_id:
        # Get the last employee ID
        last_staff = StaffProfile.objects.order_by('-employee_id').first()
        
        if last_staff and last_staff.employee_id.startswith('EMP'):
            try:
                # Extract number from last employee ID (e.g., EMP001 -> 1)
                last_number = int(last_staff.employee_id[3:])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        # Generate new employee ID with zero padding (EMP001, EMP002, etc.)
        instance.employee_id = f'EMP{new_number:03d}'


@receiver(pre_save, sender=SavingsAccount)
def generate_account_number(sender, instance, **kwargs):
    """Auto-generate savings account number"""
    if not instance.account_number:
        # Format: SAV + Year + 6-digit sequential number
        # Example: SAV2025000001
        year = timezone.now().year
        last_account = SavingsAccount.objects.filter(
            account_number__startswith=f'SAV{year}'
        ).order_by('-account_number').first()
        
        if last_account:
            try:
                # Extract sequence number from account (e.g., SAV2025000001 -> 1)
                last_seq = int(last_account.account_number[-6:])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        
        instance.account_number = f'SAV{year}{new_seq:06d}'


@receiver(pre_save, sender=Loan)
def generate_loan_number(sender, instance, **kwargs):
    """Auto-generate loan number"""
    if not instance.loan_number:
        # Format: LON + Year + 6-digit sequential number
        # Example: LON2025000001
        year = timezone.now().year
        last_loan = Loan.objects.filter(
            loan_number__startswith=f'LON{year}'
        ).order_by('-loan_number').first()
        
        if last_loan:
            try:
                # Extract sequence number
                last_seq = int(last_loan.loan_number[-6:])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        
        instance.loan_number = f'LON{year}{new_seq:06d}'


@receiver(pre_save, sender=Transaction)
def generate_transaction_ref(sender, instance, **kwargs):
    """Auto-generate transaction reference"""
    if not instance.transaction_ref:
        # Format: TXN + Year + Month + Day + Hour + Minute + Second + Random 4 chars
        # Example: TXN20251128143025AB3D
        now = timezone.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        random_str = get_random_string(4, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        instance.transaction_ref = f'TXN{timestamp}{random_str}'


# ============================================
# NOTIFICATION TRIGGERS
# ============================================

@receiver(post_save, sender=User)
def notify_client_registration(sender, instance, created, **kwargs):
    """Notify manager when new client is registered"""
    if created and instance.user_role == 'client':
        # Get the manager of the branch
        if instance.branch:
            managers = User.objects.filter(
                branch=instance.branch,
                user_role='manager',
                is_active=True
            )
            
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='client_registered',
                    title='New Client Registration',
                    message=f'New client {instance.get_full_name()} has been registered and requires approval.',
                    related_client=instance,
                    is_urgent=True
                )


@receiver(post_save, sender=Loan)
def notify_loan_application(sender, instance, created, **kwargs):
    """Notify manager when loan is applied"""
    if created and instance.status == 'pending':
        # Notify manager of the branch
        if instance.branch:
            managers = User.objects.filter(
                branch=instance.branch,
                user_role='manager',
                is_active=True
            )
            
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='loan_applied',
                    title='New Loan Application',
                    message=f'Loan application of ₦{instance.principal_amount:,.2f} from {instance.client.get_full_name()} requires approval.',
                    related_loan=instance,
                    related_client=instance.client,
                    is_urgent=True
                )


@receiver(post_save, sender=Loan)
def notify_loan_approval(sender, instance, update_fields, **kwargs):
    """Notify officer when loan is approved/rejected"""
    if not kwargs.get('created') and instance.status in ['approved', 'rejected']:
        # Notify the officer who created the loan
        if instance.created_by:
            if instance.status == 'approved':
                Notification.objects.create(
                    user=instance.created_by,
                    notification_type='loan_approved',
                    title='Loan Approved',
                    message=f'Loan {instance.loan_number} for {instance.client.get_full_name()} has been approved.',
                    related_loan=instance,
                    related_client=instance.client
                )
            elif instance.status == 'rejected':
                Notification.objects.create(
                    user=instance.created_by,
                    notification_type='loan_rejected',
                    title='Loan Rejected',
                    message=f'Loan {instance.loan_number} for {instance.client.get_full_name()} has been rejected.',
                    related_loan=instance,
                    related_client=instance.client
                )


@receiver(post_save, sender=Loan)
def notify_loan_overdue(sender, instance, **kwargs):
    """Notify stakeholders when loan becomes overdue"""
    if not kwargs.get('created') and instance.status == 'overdue':
        # Notify officer
        if instance.created_by:
            Notification.objects.create(
                user=instance.created_by,
                notification_type='loan_overdue',
                title='Loan Overdue Alert',
                message=f'Loan {instance.loan_number} for {instance.client.get_full_name()} is {instance.days_overdue} days overdue.',
                related_loan=instance,
                related_client=instance.client,
                is_urgent=True
            )
        
        # Notify manager
        if instance.branch:
            managers = User.objects.filter(
                branch=instance.branch,
                user_role='manager',
                is_active=True
            )
            
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='loan_overdue',
                    title='Loan Overdue Alert',
                    message=f'Loan {instance.loan_number} is {instance.days_overdue} days overdue. Outstanding: ₦{instance.outstanding_balance:,.2f}',
                    related_loan=instance,
                    related_client=instance.client,
                    is_urgent=True
                )


@receiver(post_save, sender=SavingsAccount)
def notify_savings_creation(sender, instance, created, **kwargs):
    """Notify manager when savings account is created"""
    if created and instance.status == 'pending':
        # Notify manager
        if instance.branch:
            managers = User.objects.filter(
                branch=instance.branch,
                user_role='manager',
                is_active=True
            )
            
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='savings_created',
                    title='New Savings Account',
                    message=f'Savings account for {instance.client.get_full_name()} requires approval.',
                    related_savings=instance,
                    related_client=instance.client,
                    is_urgent=True
                )