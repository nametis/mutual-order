import redis
import json
import hashlib
from functools import wraps
from flask import current_app

class CacheService:
    """Redis cache service"""
    
    def __init__(self):
        self.redis_client = None
        self._initialized = False
    
    def _setup_redis(self):
        """Setup Redis connection - only call within app context"""
        if self._initialized:
            return
            
        try:
            from flask import current_app
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            
            # Debug: Show what URL we're trying to connect to
            current_app.logger.info(f"🔍 Attempting Redis connection to: {redis_url}")
            
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            current_app.logger.info("✅ Redis connected successfully")
        except RuntimeError:
            # No app context - skip Redis setup for now
            print("⚠️ Redis setup skipped - no app context available")
            return
        except Exception as e:
            # Redis connection failed
            try:
                from flask import current_app
                redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
                current_app.logger.warning(f"⚠️ Redis connection failed to {redis_url}: {e}")
            except RuntimeError:
                print(f"⚠️ Redis not available - caching disabled: {e}")
            self.redis_client = None
        finally:
            self._initialized = True
    
    def is_available(self):
        """Check if Redis is available"""
        if not self._initialized:
            self._setup_redis()
        return self.redis_client is not None
    
    def get(self, key):
        """Get value from cache"""
        if not self.is_available():
            return None
        
        try:
            cached = self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.warning(f"Cache get error: {e}")
            except RuntimeError:
                print(f"Cache get error: {e}")
        
        return None
    
    def set(self, key, value, expire_seconds=3600):
        """Set value in cache with expiration"""
        if not self.is_available():
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(key, expire_seconds, serialized)
            return True
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.warning(f"Cache set error: {e}")
            except RuntimeError:
                print(f"Cache set error: {e}")
            return False
    
    def delete(self, key):
        """Delete key from cache"""
        if not self.is_available():
            return False
        
        try:
            return self.redis_client.delete(key)
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.warning(f"Cache delete error: {e}")
            except RuntimeError:
                print(f"Cache delete error: {e}")
            return False
    
    def flush_all(self):
        """Clear all cache (use with caution)"""
        if not self.is_available():
            return False
        
        try:
            return self.redis_client.flushall()
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.warning(f"Cache flush error: {e}")
            except RuntimeError:
                print(f"Cache flush error: {e}")
            return False
    
    def generate_key(self, prefix, *args, **kwargs):
        """Generate a cache key from function name and arguments"""
        # Create a string representation of all arguments
        args_str = str(args) + str(sorted(kwargs.items()))
        
        # Create hash to avoid key length issues
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        
        return f"cache:{prefix}:{args_hash}"


# Global cache service instance
cache_service = CacheService()


def cache_result(expire_seconds=3600, key_prefix=None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine key prefix
            prefix = key_prefix or func.__name__
            
            # Generate cache key
            cache_key = cache_service.generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, expire_seconds)
            
            return result
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern):
    """Invalidate all cache keys matching a pattern"""
    if not cache_service.is_available():
        return False
    
    try:
        keys = cache_service.redis_client.keys(f"cache:{pattern}:*")
        if keys:
            cache_service.redis_client.delete(*keys)
        return True
    except Exception as e:
        current_app.logger.warning(f"Cache invalidation error: {e}")
        return False


def cache_key_exists(key):
    """Check if a cache key exists"""
    if not cache_service.is_available():
        return False
    
    try:
        return cache_service.redis_client.exists(key)
    except Exception as e:
        current_app.logger.warning(f"Cache exists check error: {e}")
        return False