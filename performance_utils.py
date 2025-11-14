"""
Performance utilities for Telegram Media Downloader
Includes rate limiting, retry logic, download optimization, and metrics
"""

import asyncio
import time
from typing import Callable, Optional, Dict, Any
from functools import wraps
from datetime import datetime, timedelta
from collections import deque
import logging


class RateLimiter:
    """
    Adaptive rate limiter for Telegram API calls
    Automatically adjusts to avoid FloodWait errors
    """

    def __init__(
        self,
        calls_per_second: float = 1.0,
        burst_size: int = 5,
        adaptive: bool = True
    ):
        """
        Initialize rate limiter

        Args:
            calls_per_second: Maximum calls per second
            burst_size: Maximum burst size before throttling
            adaptive: Enable adaptive rate limiting
        """
        self.calls_per_second = calls_per_second
        self.burst_size = burst_size
        self.adaptive = adaptive
        self.call_times = deque(maxlen=burst_size)
        self.flood_wait_until = None
        self.logger = logging.getLogger("telegram_downloader.rate_limiter")

    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # Check if we're in flood wait period
        if self.flood_wait_until and now < self.flood_wait_until:
            wait_time = self.flood_wait_until - now
            self.logger.warning(f"Flood wait active, sleeping {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            self.flood_wait_until = None
            now = time.time()

        # Check burst limit
        if len(self.call_times) >= self.burst_size:
            oldest_call = self.call_times[0]
            time_window = now - oldest_call
            required_window = self.burst_size / self.calls_per_second

            if time_window < required_window:
                sleep_time = required_window - time_window
                self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                now = time.time()

        # Record this call
        self.call_times.append(now)

    def set_flood_wait(self, seconds: int):
        """
        Set flood wait period after receiving FloodWait error

        Args:
            seconds: Seconds to wait
        """
        self.flood_wait_until = time.time() + seconds + 1  # Add 1s buffer
        self.logger.warning(f"FloodWait set for {seconds}s")

        # Adapt rate if adaptive mode is on
        if self.adaptive and self.calls_per_second > 0.1:
            self.calls_per_second *= 0.8  # Reduce by 20%
            self.logger.info(f"Adapted rate to {self.calls_per_second:.2f} calls/s")

    def reset(self):
        """Reset rate limiter state"""
        self.call_times.clear()
        self.flood_wait_until = None


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(calls_per_second=1.0, burst_size=5)
    return _global_rate_limiter


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exponential: bool = True,
    catch_exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        exponential: Use exponential backoff
        catch_exceptions: Tuple of exceptions to catch and retry

    Usage:
        @async_retry(max_attempts=3, base_delay=2.0)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = logging.getLogger(f"telegram_downloader.retry.{func.__name__}")

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except catch_exceptions as e:
                    if attempt == max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts: {e}")
                        raise

                    # Calculate delay
                    if exponential:
                        delay = base_delay * (2 ** (attempt - 1))
                    else:
                        delay = base_delay

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

        return wrapper
    return decorator


class DownloadMetrics:
    """Track download performance metrics"""

    def __init__(self):
        self.total_downloads = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.total_bytes = 0
        self.start_time = datetime.now()
        self.download_times = []
        self.logger = logging.getLogger("telegram_downloader.metrics")

    def record_download(self, success: bool, file_size: int = 0, duration: float = 0):
        """
        Record a download operation

        Args:
            success: Whether download was successful
            file_size: Size of downloaded file in bytes
            duration: Download duration in seconds
        """
        self.total_downloads += 1

        if success:
            self.successful_downloads += 1
            self.total_bytes += file_size
            if duration > 0:
                self.download_times.append(duration)
        else:
            self.failed_downloads += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        stats = {
            "total_downloads": self.total_downloads,
            "successful": self.successful_downloads,
            "failed": self.failed_downloads,
            "success_rate": (
                (self.successful_downloads / self.total_downloads * 100)
                if self.total_downloads > 0 else 0
            ),
            "total_bytes": self.total_bytes,
            "total_mb": self.total_bytes / (1024 * 1024),
            "elapsed_seconds": elapsed,
            "average_speed_mbps": (
                (self.total_bytes / (1024 * 1024) / elapsed)
                if elapsed > 0 else 0
            ),
        }

        if self.download_times:
            stats["avg_download_time"] = sum(self.download_times) / len(self.download_times)
            stats["min_download_time"] = min(self.download_times)
            stats["max_download_time"] = max(self.download_times)

        return stats

    def log_statistics(self):
        """Log current statistics"""
        stats = self.get_statistics()
        self.logger.info(
            f"Download Statistics: {stats['successful']}/{stats['total_downloads']} successful "
            f"({stats['success_rate']:.1f}%), "
            f"{stats['total_mb']:.2f} MB downloaded, "
            f"avg speed: {stats['average_speed_mbps']:.2f} MB/s"
        )

    def reset(self):
        """Reset all metrics"""
        self.total_downloads = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.total_bytes = 0
        self.start_time = datetime.now()
        self.download_times = []


class DownloadPool:
    """
    Manages concurrent downloads with intelligent throttling
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        rate_limiter: Optional[RateLimiter] = None,
        metrics: Optional[DownloadMetrics] = None
    ):
        """
        Initialize download pool

        Args:
            max_concurrent: Maximum concurrent downloads
            rate_limiter: Rate limiter instance
            metrics: Metrics tracker instance
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.metrics = metrics or DownloadMetrics()
        self.logger = logging.getLogger("telegram_downloader.download_pool")
        self.active_downloads = 0

    async def download(
        self,
        download_func: Callable,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute a download with rate limiting and metrics

        Args:
            download_func: Async function to execute download
            *args, **kwargs: Arguments for download function

        Returns:
            Result from download function or None if failed
        """
        async with self.semaphore:
            self.active_downloads += 1
            start_time = time.time()

            try:
                # Acquire rate limit token
                await self.rate_limiter.acquire()

                # Execute download
                result = await download_func(*args, **kwargs)

                # Record success
                duration = time.time() - start_time
                file_size = kwargs.get('file_size', 0)
                self.metrics.record_download(True, file_size, duration)

                self.logger.debug(f"Download completed in {duration:.2f}s")
                return result

            except Exception as e:
                # Check for FloodWait error
                if 'FloodWaitError' in str(type(e).__name__):
                    # Extract wait time and set flood wait
                    wait_seconds = getattr(e, 'seconds', 60)
                    self.rate_limiter.set_flood_wait(wait_seconds)
                    self.logger.warning(f"FloodWaitError: waiting {wait_seconds}s")

                # Record failure
                duration = time.time() - start_time
                self.metrics.record_download(False, 0, duration)

                self.logger.error(f"Download failed after {duration:.2f}s: {e}")
                raise

            finally:
                self.active_downloads -= 1

    async def download_batch(
        self,
        download_tasks: list,
        show_progress: bool = True
    ) -> list:
        """
        Execute batch of downloads with progress tracking

        Args:
            download_tasks: List of (download_func, args, kwargs) tuples
            show_progress: Show progress information

        Returns:
            List of results (None for failed downloads)
        """
        total_tasks = len(download_tasks)
        self.logger.info(f"Starting batch download of {total_tasks} items")

        # Create coroutines
        coroutines = [
            self.download(func, *args, **kwargs)
            for func, args, kwargs in download_tasks
        ]

        # Execute with gather
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Process results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = total_tasks - successful

        self.logger.info(
            f"Batch download completed: {successful}/{total_tasks} successful, "
            f"{failed} failed"
        )

        # Log metrics
        self.metrics.log_statistics()

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.get_statistics()


class ProgressTracker:
    """Track and report progress of long-running operations"""

    def __init__(self, total: int, operation_name: str = "Operation"):
        self.total = total
        self.current = 0
        self.operation_name = operation_name
        self.start_time = datetime.now()
        self.logger = logging.getLogger("telegram_downloader.progress")

    def update(self, increment: int = 1):
        """Update progress"""
        self.current += increment
        self._log_progress()

    def _log_progress(self):
        """Log current progress"""
        if self.total == 0:
            return

        percentage = (self.current / self.total) * 100
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if self.current > 0:
            estimated_total = (elapsed / self.current) * self.total
            remaining = estimated_total - elapsed
            eta = timedelta(seconds=int(remaining))
        else:
            eta = "unknown"

        self.logger.info(
            f"{self.operation_name}: {self.current}/{self.total} "
            f"({percentage:.1f}%) - ETA: {eta}"
        )

    def complete(self):
        """Mark operation as complete"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(
            f"{self.operation_name} completed: {self.current}/{self.total} "
            f"in {elapsed:.2f}s"
        )
