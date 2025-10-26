// Notification App for header notifications
function notificationApp() {
    return {
        notifications: [],
        unreadCount: 0,
        showNotifications: false,
        
        async loadNotifications() {
            try {
                const response = await fetch('/api/notifications?limit=10');
                if (response.ok) {
                    this.notifications = await response.json();
                    this.updateUnreadCount();
                }
            } catch (error) {
                console.error('Error loading notifications:', error);
            }
        },
        
        async loadUnreadCount() {
            try {
                const response = await fetch('/api/notifications/unread-count');
                if (response.ok) {
                    const data = await response.json();
                    this.unreadCount = data.unread_count;
                }
            } catch (error) {
                console.error('Error loading unread count:', error);
            }
        },
        
        updateUnreadCount() {
            this.unreadCount = this.notifications.filter(n => !n.is_read).length;
        },
        
        toggleNotifications() {
            this.showNotifications = !this.showNotifications;
            if (this.showNotifications) {
                this.loadNotifications();
            }
        },
        
        async markAsRead(notificationId) {
            try {
                const response = await fetch(`/api/notifications/${notificationId}/read`, {
                    method: 'POST'
                });
                if (response.ok) {
                    // Update local state
                    const notification = this.notifications.find(n => n.id === notificationId);
                    if (notification) {
                        notification.is_read = true;
                        this.updateUnreadCount();
                    }
                }
            } catch (error) {
                console.error('Error marking notification as read:', error);
            }
        },
        
        handleNotificationClick(notification) {
            // If already read, don't mark again (to avoid duplicate requests)
            if (!notification.is_read) {
                // Mark as read immediately (optimistic update)
                notification.is_read = true;
                this.updateUnreadCount();
                
                // Send request to backend
                this.markAsRead(notification.id);
            }
            
            // Close dropdown
            this.showNotifications = false;
            
            // If notification has an order_id, redirect to the order page
            if (notification.order_id) {
                window.location.href = `/order/${notification.order_id}`;
            }
        },
        
        formatDate(dateString) {
            const date = new Date(dateString);
            const now = new Date();
            const diffInMinutes = Math.floor((now - date) / (1000 * 60));
            
            if (diffInMinutes < 1) {
                return 'À l\'instant';
            } else if (diffInMinutes < 60) {
                return `Il y a ${diffInMinutes} min`;
            } else if (diffInMinutes < 1440) {
                const hours = Math.floor(diffInMinutes / 60);
                return `Il y a ${hours}h`;
            } else {
                const days = Math.floor(diffInMinutes / 1440);
                return `Il y a ${days}j`;
            }
        }
    }
}

// Auto-refresh notifications every 30 seconds
document.addEventListener('DOMContentLoaded', function() {
    setInterval(() => {
        // Only refresh if there's a notification app on the page
        const notificationElements = document.querySelectorAll('[x-data*="notificationApp"]');
        if (notificationElements.length > 0) {
            // Trigger a refresh by dispatching a custom event
            window.dispatchEvent(new CustomEvent('refreshNotifications'));
        }
    }, 30000);
    
    // Listen for the refresh event
    window.addEventListener('refreshNotifications', function() {
        const notificationElements = document.querySelectorAll('[x-data*="notificationApp"]');
        notificationElements.forEach(element => {
            if (element._x_dataStack && element._x_dataStack[0]) {
                const app = element._x_dataStack[0];
                if (app.loadUnreadCount) {
                    app.loadUnreadCount();
                }
            }
        });
    });
});
