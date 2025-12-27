"""
Notification Views
Views for notification management matching UI requirements
"""

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q

from .models import Notification
from .permissions import IsAuthenticated


class NotificationSerializer:
    """Simple notification serializer"""
    
    @staticmethod
    def serialize(notification):
        """Convert notification to dict"""
        # Calculate relative time
        now = timezone.now()
        time_diff = now - notification.created_at
        
        if time_diff.seconds < 60:
            time_ago = f"{time_diff.seconds}s ago"
        elif time_diff.seconds < 3600:
            time_ago = f"{time_diff.seconds // 60}m ago"
        elif time_diff.seconds < 86400:
            time_ago = f"{time_diff.seconds // 3600}h ago"
        elif time_diff.days == 1:
            time_ago = "1d ago"
        elif time_diff.days < 7:
            time_ago = f"{time_diff.days}d ago"
        elif time_diff.days < 30:
            time_ago = f"{time_diff.days // 7}w ago"
        else:
            time_ago = f"{time_diff.days // 30}mo ago"
        
        # Determine category based on notification type
        if 'loan' in notification.notification_type:
            category = 'loans'
        elif 'deposit' in notification.notification_type or 'withdrawal' in notification.notification_type or 'savings' in notification.notification_type:
            category = 'deposits'
        else:
            category = 'others'
        
        return {
            'id': str(notification.id),
            'type': notification.notification_type,
            'category': category,
            'title': notification.title,
            'description': notification.message,
            'time': time_ago,
            'is_read': notification.is_read,
            'is_urgent': notification.is_urgent,
            'created_at': notification.created_at.isoformat(),
            'related_client_id': str(notification.related_client.id) if notification.related_client else None,
            'related_loan_id': str(notification.related_loan.id) if notification.related_loan else None,
            'related_savings_id': str(notification.related_savings.id) if notification.related_savings else None,
        }


class NotificationListView(generics.ListAPIView):
    """
    List all notifications for current user
    Supports filtering by category and read status
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category == 'loans':
            queryset = queryset.filter(
                Q(notification_type__contains='loan')
            )
        elif category == 'deposits':
            queryset = queryset.filter(
                Q(notification_type__contains='deposit') |
                Q(notification_type__contains='withdrawal') |
                Q(notification_type__contains='savings')
            )
        elif category == 'others':
            queryset = queryset.exclude(
                Q(notification_type__contains='loan') |
                Q(notification_type__contains='deposit') |
                Q(notification_type__contains='withdrawal') |
                Q(notification_type__contains='savings')
            )
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get unread count
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            notifications = [NotificationSerializer.serialize(n) for n in page]
            return self.get_paginated_response({
                'success': True,
                'unread_count': unread_count,
                'notifications': notifications
            })
        
        notifications = [NotificationSerializer.serialize(n) for n in queryset]
        return Response({
            'success': True,
            'unread_count': unread_count,
            'notifications': notifications
        }, status=status.HTTP_200_OK)


class UnreadNotificationCountView(APIView):
    """
    Get count of unread notifications
    Used for notification bell badge
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return Response({
            'success': True,
            'count': unread_count
        }, status=status.HTTP_200_OK)


class MarkNotificationAsReadView(APIView):
    """
    Mark a single notification as read
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Notification not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        notification.mark_as_read()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read.',
            'notification': NotificationSerializer.serialize(notification)
        }, status=status.HTTP_200_OK)


class MarkAllNotificationsAsReadView(APIView):
    """
    Mark all notifications as read for current user
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Get category filter if provided
        category = request.data.get('category')
        
        queryset = Notification.objects.filter(
            user=request.user,
            is_read=False
        )
        
        # Apply category filter
        if category == 'loans':
            queryset = queryset.filter(notification_type__contains='loan')
        elif category == 'deposits':
            queryset = queryset.filter(
                Q(notification_type__contains='deposit') |
                Q(notification_type__contains='withdrawal') |
                Q(notification_type__contains='savings')
            )
        elif category == 'others':
            queryset = queryset.exclude(
                Q(notification_type__contains='loan') |
                Q(notification_type__contains='deposit') |
                Q(notification_type__contains='withdrawal') |
                Q(notification_type__contains='savings')
            )
        
        # Mark all as read
        count = queryset.update(is_read=True, read_at=timezone.now())
        
        return Response({
            'success': True,
            'message': f'{count} notifications marked as read.'
        }, status=status.HTTP_200_OK)


class DeleteNotificationView(APIView):
    """
    Delete a notification
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Notification not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        notification.delete()
        
        return Response({
            'success': True,
            'message': 'Notification deleted.'
        }, status=status.HTTP_200_OK)


class DeleteAllNotificationsView(APIView):
    """
    Delete all notifications for current user
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        count = Notification.objects.filter(user=request.user).delete()[0]
        
        return Response({
            'success': True,
            'message': f'{count} notifications deleted.'
        }, status=status.HTTP_200_OK)