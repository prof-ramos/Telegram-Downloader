"""
Professional logging module for Telegram Media Downloader
Provides structured logging with rotation, multiple handlers, and detailed formatting
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }

    def format(self, record):
        """Format log record with colors for console"""
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return formatted


class TelegramLogger:
    """Centralized logging manager for the application"""

    def __init__(
        self,
        name: str = "telegram_downloader",
        log_dir: str = "logs",
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        enable_rotation: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        """
        Initialize logging system

        Args:
            name: Logger name
            log_dir: Directory for log files
            console_level: Logging level for console output
            file_level: Logging level for file output
            enable_rotation: Enable log file rotation
            max_bytes: Maximum size per log file (for RotatingFileHandler)
            backup_count: Number of backup files to keep
        """
        self.name = name
        self.log_dir = log_dir
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # Capture all levels

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        # Create log directory
        os.makedirs(log_dir, exist_ok=True)

        # Setup handlers
        self._setup_console_handler(console_level)
        self._setup_file_handlers(file_level, enable_rotation, max_bytes, backup_count)

    def _setup_console_handler(self, level: int):
        """Setup colored console handler"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Colored format for console
        console_format = ColoredFormatter(
            '%(levelname)s | %(name)s | %(message)s'
        )
        console_handler.setFormatter(console_format)

        self.logger.addHandler(console_handler)

    def _setup_file_handlers(
        self,
        level: int,
        enable_rotation: bool,
        max_bytes: int,
        backup_count: int
    ):
        """Setup file handlers with rotation"""

        # Main application log (with rotation)
        main_log_path = os.path.join(self.log_dir, f"{self.name}.log")

        if enable_rotation:
            main_handler = RotatingFileHandler(
                main_log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            main_handler = logging.FileHandler(main_log_path, encoding='utf-8')

        main_handler.setLevel(level)

        # Detailed format for files
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_handler.setFormatter(file_format)

        self.logger.addHandler(main_handler)

        # Error log (separate file for errors only)
        error_log_path = os.path.join(self.log_dir, f"{self.name}_errors.log")
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)

        self.logger.addHandler(error_handler)

        # Daily log (rotates daily)
        daily_log_path = os.path.join(
            self.log_dir,
            f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        daily_handler = TimedRotatingFileHandler(
            daily_log_path,
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.INFO)
        daily_handler.setFormatter(file_format)

        self.logger.addHandler(daily_handler)

    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance"""
        return self.logger


# Global logger instance
_global_logger: Optional[TelegramLogger] = None


def setup_logger(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    log_dir: str = "logs"
) -> logging.Logger:
    """
    Setup and return global logger instance

    Args:
        console_level: Console logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_level: File logging level
        log_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    global _global_logger

    if _global_logger is None:
        # Convert string levels to logging constants
        console_level_int = getattr(logging, console_level.upper(), logging.INFO)
        file_level_int = getattr(logging, file_level.upper(), logging.DEBUG)

        _global_logger = TelegramLogger(
            console_level=console_level_int,
            file_level=file_level_int,
            log_dir=log_dir
        )

    return _global_logger.get_logger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance for a specific module

    Args:
        name: Module name (if None, returns root logger)

    Returns:
        Logger instance
    """
    if _global_logger is None:
        setup_logger()

    if name:
        return logging.getLogger(f"telegram_downloader.{name}")

    return _global_logger.get_logger()


# Convenience functions for direct logging
def debug(msg: str, *args, **kwargs):
    """Log debug message"""
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Log info message"""
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Log warning message"""
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Log error message"""
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """Log critical message"""
    get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """Log exception with traceback"""
    get_logger().exception(msg, *args, **kwargs)


# Performance logging helper
class PerformanceLogger:
    """Context manager for logging operation performance"""

    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or get_logger()
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Started: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(f"Completed: {self.operation_name} in {elapsed:.2f}s")
        else:
            self.logger.error(
                f"Failed: {self.operation_name} after {elapsed:.2f}s - {exc_val}"
            )

        return False  # Don't suppress exceptions
