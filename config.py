"""
Configuration module for Telegram Media Downloader
Contains API credentials and application settings
"""

import os

# Telegram API credentials - Replace with your actual values
# Get these from https://my.telegram.org/apps
API_ID = 27031784  # Replace with your API ID
API_HASH = "8a5c5a5d72783ac32fc40426b2a4316c"  # Replace with your API Hash

# Application settings
SESSION_NAME = "telegram_downloader_session"
EXPORTS_DIR = "exports"
DEFAULT_LIMIT_PER_CHAT = 1000

# File size limits (in bytes)
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB default limit

# Download settings
ENABLE_PROGRESS_BAR = True
CONCURRENT_DOWNLOADS = 3  # Increased from 1 to 3 for better performance

# Logging settings
LOG_DIRECTORY = "logs"
CONSOLE_LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
FILE_LOG_LEVEL = "DEBUG"  # More detailed logging in files
ENABLE_LOG_ROTATION = True
MAX_LOG_SIZE_MB = 10  # Maximum size per log file before rotation
LOG_BACKUP_COUNT = 5  # Number of backup log files to keep

# Performance settings
RATE_LIMIT_CALLS_PER_SECOND = 1.0  # API calls per second
RATE_LIMIT_BURST_SIZE = 5  # Burst size before throttling
ENABLE_ADAPTIVE_RATE_LIMITING = True  # Automatically adjust on FloodWait
RETRY_MAX_ATTEMPTS = 3  # Maximum retry attempts for failed operations
RETRY_BASE_DELAY = 1.0  # Base delay in seconds for retry backoff

# Supported media types
SUPPORTED_MEDIA_TYPES = ["photo", "video", "document", "audio", "voice", "sticker"]

# Directory names for different media types
MEDIA_DIRECTORIES = {
    "photo": "fotos",
    "video": "videos",
    "document": "documentos",
    "audio": "audio",
    "voice": "mensagens_voz",
    "sticker": "stickers",
    "other": "outros",
}
