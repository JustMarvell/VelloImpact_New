import requests
import discord
import asyncio
import settings
import firebase_admin
from firebase_admin import credentials, db
import logging
import random
import time
from functools import wraps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging
logger = logging.getLogger("firebase")

# Global session with retry strategy
FIREBASE_SESSION = requests.Session()

# Configure retry strategy for connection issues
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504, 520, 522, 524],  # Include CloudFlare errors
    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
    backoff_factor=1,
    raise_on_status=False
)

adapter = HTTPAdapter(max_retries=retry_strategy)
FIREBASE_SESSION.mount("http://", adapter)
FIREBASE_SESSION.mount("https://", adapter)

# Default timeout
DEFAULT_TIMEOUT = 30

def retry_on_connection_error(max_retries=3, delay=1):
    """Decorator for retrying on connection/TLS errors"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check for connection-related errors
                    if any(keyword in error_msg for keyword in [
                        'connection', 'tls', 'reset', 'timeout', 'network', 
                        'unreachable', 'temporary failure', 'name resolution'
                    ]):
                        if attempt < max_retries - 1:
                            wait_time = delay * (2 ** attempt) + random.uniform(0, 1)
                            logger.warning(f"Connection error in {func.__name__}, retrying in {wait_time:.2f}s: {e}")
                            await asyncio.sleep(wait_time)
                            continue
                    # Re-raise non-connection errors immediately
                    raise e
            raise Exception(f"Max retries exceeded for {func.__name__}")
        return wrapper
    return decorator

class CircuitBreaker:
    """Circuit breaker for network operations"""
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker moved to HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker moved to OPEN state after {self.failure_count} failures")

# Global circuit breaker for Firebase operations
firebase_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)

@retry_on_connection_error(max_retries=3, delay=1)
async def safe_firebase_request(request_func, *args, **kwargs):
    """Wrapper for Firebase requests with retry logic"""
    try:
        # Add timeout to prevent hanging
        if 'timeout' not in kwargs:
            kwargs['timeout'] = DEFAULT_TIMEOUT
        
        return request_func(*args, **kwargs)
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'tls', 'reset', 'timeout']):
            logger.warning(f"TLS/Connection error in Firebase request: {e}")
        raise e

async def check_status():
    """Check Firebase status with retry logic and circuit breaker"""
    async def _check_status_impl():
        response = FIREBASE_SESSION.get(
            settings.FIREBASE_API_SECRET + "/test_data/status.json",
            timeout=DEFAULT_TIMEOUT
        )
        if response.status_code == 200:
            return str(response.json())
        return "NONE"
    
    try:
        result = await firebase_circuit_breaker.call(_check_status_impl)
        return result
    except Exception as e:
        logger.error(f"Failed to check Firebase status: {e}")
        return "ERROR"
    
@retry_on_connection_error(max_retries=3, delay=0.5)
async def wait_for_result(path, key=None, expected_type=None, timeout=10):
    """Wait for Firebase result with retry logic"""
    for _ in range(timeout * 2):
        try:
            response = FIREBASE_SESSION.get(path, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if expected_type and not isinstance(data, expected_type):
                    await asyncio.sleep(0.5)
                    continue
                return data[key] if key else data
        except Exception as e:
            logger.debug(f"Error in wait_for_result, retrying: {e}")
        await asyncio.sleep(0.5)
    return None 

async def check_network_health():
    """Check if Firebase connection is healthy"""
    try:
        test_response = FIREBASE_SESSION.get(
            "https://firebase.google.com", 
            timeout=5
        )
        return test_response.status_code == 200
    except Exception as e:
        logger.warning(f"Firebase network health check failed: {e}")
        return False

def initialize_app():
    """Initialize Firebase with improved error handling"""
    try:
        cred = credentials.Certificate(f'{settings.BASE_DIR}/key.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL' : f'{settings.FIREBASE_API_SECRET}'
        })
        logger.info("Firebase initialized successfully")
        
        # Note: Connection testing is handled by the network monitoring system
        # No need for manual background testing here
        
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        logger.warning("Continuing without Firebase functionality")
        # Don't re-raise - allow bot to continue without Firebase

# Export global session for use in other modules
__all__ = [
    'FIREBASE_SESSION', 
    'DEFAULT_TIMEOUT', 
    'check_status', 
    'wait_for_result', 
    'initialize_app',
    'check_network_health',
    'safe_firebase_request',
    'firebase_circuit_breaker',
    'retry_on_connection_error'
]
