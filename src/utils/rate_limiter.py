"""
Rate Limiting Handler

Manages API rate limits using a token bucket algorithm
with persistent state and adaptive backoff.
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
from .config import ConfigManager

logger = logging.getLogger(__name__)

class RateLimiter:
    """Handles API rate limiting"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.state_file = Path(
            self.config.get_value(
                'rate_limiting.state_file',
                'rate_limit_state.json'
            )
        )
        self.buckets: Dict[str, Dict] = {}
        self.load_state()
    
    def load_state(self):
        """Load rate limit state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    saved_state = json.load(f)
                    
                # Convert saved timestamps back to float
                for bucket in saved_state.values():
                    bucket['last_update'] = float(
                        bucket['last_update']
                    )
                
                self.buckets = saved_state
                
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(
                f"Failed to load rate limit state: {e}"
            )
            self.buckets = {}
    
    def save_state(self):
        """Save current rate limit state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.buckets, f)
        except IOError as e:
            logger.error(
                f"Failed to save rate limit state: {e}"
            )
    
    def get_bucket(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float
    ) -> Dict:
        """
        Get or create rate limit bucket
        
        Args:
            key: Bucket identifier
            max_tokens: Maximum tokens allowed
            refill_rate: Token refill rate per second
            
        Returns:
            Dict with bucket state
        """
        if key not in self.buckets:
            self.buckets[key] = {
                'tokens': max_tokens,
                'max_tokens': max_tokens,
                'refill_rate': refill_rate,
                'last_update': time.time()
            }
        return self.buckets[key]
    
    def update_bucket(self, bucket: Dict):
        """
        Update bucket token count based on elapsed time
        
        Args:
            bucket: Bucket to update
        """
        now = time.time()
        elapsed = now - bucket['last_update']
        
        new_tokens = elapsed * bucket['refill_rate']
        bucket['tokens'] = min(
            bucket['tokens'] + new_tokens,
            bucket['max_tokens']
        )
        bucket['last_update'] = now
    
    def check_rate_limit(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        cost: float = 1.0
    ) -> Optional[float]:
        """
        Check if action is allowed by rate limit
        
        Args:
            key: Rate limit bucket identifier
            max_tokens: Maximum tokens allowed
            refill_rate: Token refill rate per second
            cost: Token cost for this action
            
        Returns:
            Seconds to wait if rate limited, None if allowed
        """
        bucket = self.get_bucket(key, max_tokens, refill_rate)
        self.update_bucket(bucket)
        
        if bucket['tokens'] >= cost:
            bucket['tokens'] -= cost
            self.save_state()
            return None
            
        # Calculate wait time
        needed = cost - bucket['tokens']
        wait_time = needed / bucket['refill_rate']
        
        return wait_time
    
    def apply_backoff(
        self,
        wait_time: float,
        retries: int
    ) -> float:
        """
        Apply exponential backoff to wait time
        
        Args:
            wait_time: Base wait time
            retries: Number of retries so far
            
        Returns:
            Updated wait time with backoff
        """
        multiplier = self.config.get_value(
            'rate_limiting.backoff_multiplier',
            2.0
        )
        max_backoff = self.config.get_value(
            'rate_limiting.max_backoff',
            3600
        )
        
        backoff = wait_time * (multiplier ** retries)
        return min(backoff, max_backoff)
    
    def wait_if_needed(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        cost: float = 1.0
    ) -> None:
        """
        Wait if rate limited
        
        Args:
            key: Rate limit bucket identifier
            max_tokens: Maximum tokens allowed 
            refill_rate: Token refill rate per second
            cost: Token cost for this action
        """
        retries = 0
        while True:
            wait_time = self.check_rate_limit(
                key, max_tokens, refill_rate, cost
            )
            
            if wait_time is None:
                break
                
            wait_time = self.apply_backoff(wait_time, retries)
            logger.info(
                f"Rate limited on {key}, "
                f"waiting {wait_time:.1f}s"
            )
            
            time.sleep(wait_time)
            retries += 1