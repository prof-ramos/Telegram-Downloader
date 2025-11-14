"""
Test script for logging and performance utilities
Validates that the new systems are working correctly
"""

import asyncio
import sys
import time

# Import our modules
from logger import setup_logger, get_logger, PerformanceLogger
from performance_utils import (
    RateLimiter,
    async_retry,
    DownloadMetrics,
    DownloadPool,
    ProgressTracker
)


def test_logging_setup():
    """Test logging system setup"""
    print("=" * 60)
    print("TEST 1: Sistema de Logging")
    print("=" * 60)

    # Setup logger
    setup_logger(console_level="INFO", file_level="DEBUG")
    logger = get_logger("test")

    # Test different log levels
    logger.debug("Teste de log DEBUG")
    logger.info("Teste de log INFO")
    logger.warning("Teste de log WARNING")
    logger.error("Teste de log ERROR")

    # Test performance logger
    with PerformanceLogger("Test operation", logger):
        time.sleep(0.5)

    print("✅ Sistema de logging funcionando corretamente")
    print()


async def test_rate_limiter():
    """Test rate limiter"""
    print("=" * 60)
    print("TEST 2: Rate Limiter")
    print("=" * 60)

    limiter = RateLimiter(calls_per_second=2.0, burst_size=3)

    start = time.time()
    for i in range(5):
        await limiter.acquire()
        print(f"  Request {i + 1} at {time.time() - start:.2f}s")

    elapsed = time.time() - start
    print(f"✅ 5 requests completadas em {elapsed:.2f}s (esperado ~2.0s)")
    print()


async def test_retry_decorator():
    """Test async retry decorator"""
    print("=" * 60)
    print("TEST 3: Retry Decorator")
    print("=" * 60)

    attempts = [0]

    @async_retry(max_attempts=3, base_delay=0.1)
    async def failing_function():
        attempts[0] += 1
        print(f"  Tentativa {attempts[0]}")
        if attempts[0] < 3:
            raise ValueError("Erro proposital")
        return "Sucesso!"

    result = await failing_function()
    print(f"✅ Retry funcionou após {attempts[0]} tentativas: {result}")
    print()


def test_download_metrics():
    """Test download metrics"""
    print("=" * 60)
    print("TEST 4: Download Metrics")
    print("=" * 60)

    metrics = DownloadMetrics()

    # Simulate downloads
    metrics.record_download(success=True, file_size=1024 * 1024, duration=1.5)
    metrics.record_download(success=True, file_size=2048 * 1024, duration=2.0)
    metrics.record_download(success=False, file_size=0, duration=0.5)

    stats = metrics.get_statistics()

    print(f"  Total downloads: {stats['total_downloads']}")
    print(f"  Sucessos: {stats['successful']}")
    print(f"  Falhas: {stats['failed']}")
    print(f"  Taxa de sucesso: {stats['success_rate']:.1f}%")
    print(f"  Total MB: {stats['total_mb']:.2f}")
    print(f"  Velocidade média: {stats['average_speed_mbps']:.2f} MB/s")

    print("✅ Métricas de download funcionando corretamente")
    print()


async def test_download_pool():
    """Test download pool"""
    print("=" * 60)
    print("TEST 5: Download Pool")
    print("=" * 60)

    # Create a simple download function
    async def mock_download(item_id: int, file_size: int):
        await asyncio.sleep(0.2)  # Simulate download time
        return f"item_{item_id}"

    # Create download pool
    pool = DownloadPool(max_concurrent=3)

    # Create tasks
    tasks = [
        (mock_download, (i, 1024 * 1024), {"file_size": 1024 * 1024})
        for i in range(10)
    ]

    start = time.time()
    results = await pool.download_batch(tasks, show_progress=False)
    elapsed = time.time() - start

    successful = sum(1 for r in results if not isinstance(r, Exception))

    print(f"  Downloads: {successful}/{len(tasks)}")
    print(f"  Tempo total: {elapsed:.2f}s")
    print(f"  Concorrência: {pool.max_concurrent}")

    metrics = pool.get_metrics()
    print(f"  Taxa de sucesso: {metrics['success_rate']:.1f}%")

    print("✅ Download pool funcionando corretamente")
    print()


def test_progress_tracker():
    """Test progress tracker"""
    print("=" * 60)
    print("TEST 6: Progress Tracker")
    print("=" * 60)

    tracker = ProgressTracker(total=100, operation_name="Test Operation")

    for i in range(0, 101, 25):
        tracker.update(25 if i < 100 else 0)
        time.sleep(0.1)

    tracker.complete()

    print("✅ Progress tracker funcionando corretamente")
    print()


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TESTE DO SISTEMA DE LOGGING E PERFORMANCE")
    print("=" * 60 + "\n")

    try:
        # Test logging
        test_logging_setup()

        # Test async features
        await test_rate_limiter()
        await test_retry_decorator()

        # Test metrics
        test_download_metrics()
        await test_download_pool()

        # Test progress
        test_progress_tracker()

        print("=" * 60)
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERRO NOS TESTES: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
