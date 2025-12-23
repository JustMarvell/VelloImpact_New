import requests
import asyncio
import logging
import time
from typing import Dict, Optional, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("network")

# Global session configuration
GLOBAL_SESSION = requests.Session()

# Configure global retry strategy
global_retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504, 520, 522, 524],
    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
    raise_on_status=False
)

global_adapter = HTTPAdapter(max_retries=global_retry_strategy)
GLOBAL_SESSION.mount("http://", global_adapter)
GLOBAL_SESSION.mount("https://", global_adapter)

# Default timeout configuration
DEFAULT_TIMEOUT = 30
CONNECT_TIMEOUT = 10

class NetworkHealthMonitor:
    """Monitor network connectivity and service health"""
    
    def __init__(self):
        self.services = {
            'google': 'https://www.google.com',
            'youtube': 'https://www.youtube.com',
            'github': 'https://github.com',
            'firebase': 'https://firebase.google.com'
        }
        self.health_status = {}
        self.last_check = {}
        
    async def check_service_health(self, service_name: str, url: str) -> bool:
        """Check health of a specific service"""
        try:
            response = GLOBAL_SESSION.get(url, timeout=5)
            is_healthy = response.status_code == 200
            self.health_status[service_name] = is_healthy
            self.last_check[service_name] = time.time()
            return is_healthy
        except Exception as e:
            logger.warning(f"Health check failed for {service_name}: {e}")
            self.health_status[service_name] = False
            self.last_check[service_name] = time.time()
            return False
    
    async def check_all_services(self) -> Dict[str, bool]:
        """Check health of all monitored services"""
        results = {}
        for service_name, url in self.services.items():
            results[service_name] = await self.check_service_health(service_name, url)
        return results
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of network health"""
        overall_healthy = all(self.health_status.values()) if self.health_status else False
        
        return {
            'overall_healthy': overall_healthy,
            'service_status': self.health_status.copy(),
            'last_check': self.last_check.copy(),
            'total_services': len(self.services),
            'healthy_services': sum(1 for status in self.health_status.values() if status)
        }

# Global network monitor instance
network_monitor = NetworkHealthMonitor()

async def safe_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a safe HTTP request with retry logic and timeout"""
    # Set default timeout if not provided
    if 'timeout' not in kwargs:
        kwargs['timeout'] = DEFAULT_TIMEOUT
    
    try:
        response = GLOBAL_SESSION.request(method, url, **kwargs)
        return response
    except Exception as e:
        logger.error(f"Request failed for {url}: {e}")
        raise

async def check_network_connectivity() -> Dict[str, Any]:
    """Comprehensive network connectivity check"""
    try:
        # Check basic connectivity
        basic_check = await safe_request('GET', 'https://httpbin.org/status/200', timeout=5)
        basic_ok = basic_check.status_code == 200
        
        # Check service health
        service_health = await network_monitor.check_all_services()
        
        # Overall connectivity assessment
        overall_ok = basic_ok and any(service_health.values())
        
        return {
            'basic_connectivity': basic_ok,
            'service_health': service_health,
            'overall_connectivity': overall_ok,
            'timestamp': time.time()
        }
    except Exception as e:
        logger.error(f"Network connectivity check failed: {e}")
        return {
            'basic_connectivity': False,
            'service_health': {},
            'overall_connectivity': False,
            'error': str(e),
            'timestamp': time.time()
        }

async def monitor_network_health():
    """Background task to monitor network health"""
    while True:
        try:
            health_report = await check_network_connectivity()
            
            if not health_report['overall_connectivity']:
                logger.warning(f"Network connectivity issues detected: {health_report}")
            elif health_report['basic_connectivity']:
                logger.debug("Network connectivity is healthy")
            
            # Log service-specific issues
            for service, is_healthy in health_report.get('service_health', {}).items():
                if not is_healthy:
                    logger.warning(f"Service {service} is not responding")
            
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Network monitoring error: {e}")
            await asyncio.sleep(60)  # Wait longer on error

# Export utilities
__all__ = [
    'GLOBAL_SESSION',
    'DEFAULT_TIMEOUT',
    'CONNECT_TIMEOUT',
    'network_monitor',
    'safe_request',
    'check_network_connectivity',
    'monitor_network_health'
]
