"""
Background job service for wantlist matching and seller inventory updates
"""
import schedule
import time
import threading
from datetime import datetime, timedelta, timezone
from flask import current_app
from models import Order, User
from services import wantlist_matching_service, discogs_service

class BackgroundJobService:
    """Service for managing background jobs"""
    
    def __init__(self):
        self.running = False
        self.job_thread = None
        self.last_run = {}
    
    def start_scheduler(self):
        """Start the background job scheduler"""
        if self.running:
            return
            
        self.running = True
        
        # Schedule jobs
        schedule.every().day.at("02:00").do(self.refresh_all_seller_inventories)
        schedule.every().day.at("03:00").do(self.refresh_all_user_wantlists)
        schedule.every().day.at("04:00").do(self.cleanup_old_cache)
        schedule.every(6).hours.do(self.refresh_active_sellers)
        
        # Start job thread
        self.job_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.job_thread.start()
        
        current_app.logger.info("🕐 Background job scheduler started")
    
    def stop_scheduler(self):
        """Stop the background job scheduler"""
        self.running = False
        if self.job_thread:
            self.job_thread.join(timeout=5)
        current_app.logger.info("🛑 Background job scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                current_app.logger.error(f"Error in background job scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def refresh_all_seller_inventories(self):
        """Refresh all seller inventories (nightly at 2 AM)"""
        try:
            current_app.logger.info("🌙 Starting nightly seller inventory refresh")
            start_time = datetime.now(timezone.utc)
            
            # Get all open orders
            open_orders = Order.query.filter(
                Order.status.in_(['building', 'validation'])
            ).all()
            
            refreshed_count = 0
            for order in open_orders:
                try:
                    # No longer skipping large sellers - incremental updates handle them efficiently
                    
                    # Get a user with Discogs credentials for API calls
                    user = User.query.filter(
                        User.discogs_access_token.isnot(None),
                        User.discogs_access_secret.isnot(None)
                    ).first()
                    
                    if not user:
                        current_app.logger.warning("No user with Discogs credentials found")
                        continue
                    
                    # Force refresh seller inventory
                    inventory, metadata = wantlist_matching_service.force_refresh_seller_inventory(
                        order.seller_name,
                        user.id,
                        user.discogs_access_token,
                        user.discogs_access_secret
                    )
                    
                    if inventory:
                        refreshed_count += 1
                        current_app.logger.info(f"✅ Refreshed {order.seller_name}: {len(inventory)} items")
                    else:
                        current_app.logger.warning(f"❌ Failed to refresh {order.seller_name}")
                    
                    # Rate limiting - wait between sellers (reduced due to incremental updates)
                    time.sleep(1)
                    
                except Exception as e:
                    current_app.logger.error(f"Error refreshing {order.seller_name}: {e}")
                    continue
            
            duration = datetime.now(timezone.utc) - start_time
            current_app.logger.info(f"🌙 Nightly seller refresh completed: {refreshed_count} sellers in {duration}")
            self.last_run['seller_inventories'] = datetime.now(timezone.utc)
            
        except Exception as e:
            current_app.logger.error(f"Error in nightly seller inventory refresh: {e}")
    
    def refresh_all_user_wantlists(self):
        """Refresh all user wantlists (nightly at 3 AM)"""
        try:
            current_app.logger.info("🌙 Starting nightly wantlist refresh")
            start_time = datetime.now(timezone.utc)
            
            # Get all users with Discogs credentials
            users = User.query.filter(
                User.discogs_access_token.isnot(None),
                User.discogs_access_secret.isnot(None),
                User.discogs_username.isnot(None)
            ).all()
            
            refreshed_count = 0
            for user in users:
                try:
                    # Refresh wantlist
                    wantlist = discogs_service.get_user_wantlist(
                        user.id,
                        user.discogs_username,
                        user.discogs_access_token,
                        user.discogs_access_secret
                    )
                    
                    if wantlist:
                        refreshed_count += 1
                        current_app.logger.info(f"✅ Refreshed wantlist for {user.username}: {len(wantlist)} items")
                    else:
                        current_app.logger.warning(f"❌ Failed to refresh wantlist for {user.username}")
                    
                    # Rate limiting - wait between users
                    time.sleep(1)
                    
                except Exception as e:
                    current_app.logger.error(f"Error refreshing wantlist for {user.username}: {e}")
                    continue
            
            duration = datetime.now(timezone.utc) - start_time
            current_app.logger.info(f"🌙 Nightly wantlist refresh completed: {refreshed_count} users in {duration}")
            self.last_run['user_wantlists'] = datetime.now(timezone.utc)
            
        except Exception as e:
            current_app.logger.error(f"Error in nightly wantlist refresh: {e}")
    
    def refresh_active_sellers(self):
        """Refresh active sellers every 6 hours"""
        try:
            current_app.logger.info("🔄 Refreshing active sellers")
            
            # Get recent orders (last 7 days)
            recent_orders = Order.query.filter(
                Order.status.in_(['building', 'validation']),
                Order.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
            ).all()
            
            # Get unique sellers
            sellers = list(set([order.seller_name for order in recent_orders]))
            
            refreshed_count = 0
            for seller_name in sellers[:10]:  # Increased limit - incremental updates are efficient
                try:
                    # No longer skipping large sellers - incremental updates handle them efficiently
                    
                    # Get a user with Discogs credentials
                    user = User.query.filter(
                        User.discogs_access_token.isnot(None),
                        User.discogs_access_secret.isnot(None)
                    ).first()
                    
                    if not user:
                        continue
                    
                    # Background refresh
                    inventory, metadata = wantlist_matching_service.background_refresh_seller(
                        seller_name,
                        user.id,
                        user.discogs_access_token,
                        user.discogs_access_secret
                    )
                    
                    if inventory:
                        refreshed_count += 1
                        current_app.logger.info(f"✅ Refreshed active seller {seller_name}")
                    
                    time.sleep(0.5)  # Rate limiting (reduced due to incremental updates)
                    
                except Exception as e:
                    current_app.logger.error(f"Error refreshing active seller {seller_name}: {e}")
                    continue
            
            current_app.logger.info(f"🔄 Active seller refresh completed: {refreshed_count} sellers")
            self.last_run['active_sellers'] = datetime.now(timezone.utc)
            
        except Exception as e:
            current_app.logger.error(f"Error in active seller refresh: {e}")
    
    def cleanup_old_cache(self):
        """Clean up old cache entries (nightly at 4 AM)"""
        try:
            current_app.logger.info("🧹 Starting cache cleanup")
            
            # This would need to be implemented based on your cache backend
            # For Redis, you could remove keys older than 7 days
            current_app.logger.info("🧹 Cache cleanup completed")
            self.last_run['cache_cleanup'] = datetime.now(timezone.utc)
            
        except Exception as e:
            current_app.logger.error(f"Error in cache cleanup: {e}")
    
    def get_job_status(self):
        """Get status of background jobs"""
        return {
            'running': self.running,
            'last_run': self.last_run,
            'next_jobs': [
                str(job.next_run) for job in schedule.jobs
            ]
        }
    
    def trigger_manual_refresh(self, job_type):
        """Manually trigger a specific job"""
        try:
            if job_type == 'seller_inventories':
                self.refresh_all_seller_inventories()
            elif job_type == 'user_wantlists':
                self.refresh_all_user_wantlists()
            elif job_type == 'active_sellers':
                self.refresh_active_sellers()
            elif job_type == 'cache_cleanup':
                self.cleanup_old_cache()
            else:
                raise ValueError(f"Unknown job type: {job_type}")
            
            return True
        except Exception as e:
            current_app.logger.error(f"Error in manual job trigger: {e}")
            return False

# Global service instance
background_job_service = BackgroundJobService()

