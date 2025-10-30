"""
Colored logging configuration for terminal output.
Provides colored output for different types of plugin communications.
"""

import logging
import sys
from typing import Optional


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'

    # Regular colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


# Plugin-specific colors
PLUGIN_COLORS = {
    'wikipedia': Colors.BRIGHT_BLUE,
    'reranker': Colors.CYAN,
    'classification': Colors.YELLOW,
    'llm': Colors.GREEN,
    'security': Colors.MAGENTA,
    'default': Colors.WHITE
}


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log output."""

    # Level colors
    LEVEL_COLORS = {
        'DEBUG': Colors.BRIGHT_BLACK,
        'INFO': Colors.WHITE,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.BRIGHT_RED + Colors.BOLD,
    }

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """
        Initialize colored formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        if datefmt is None:
            datefmt = '%Y-%m-%d %H:%M:%S'
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record

        Returns:
            Formatted and colored log message
        """
        # Get level color
        level_color = self.LEVEL_COLORS.get(record.levelname, Colors.WHITE)

        # Get plugin color if specified in extra
        plugin_color = None
        if hasattr(record, 'plugin_type'):
            plugin_color = PLUGIN_COLORS.get(record.plugin_type, PLUGIN_COLORS['default'])

        # Format the base message
        formatted = super().format(record)

        # Apply plugin color if available, otherwise level color
        if plugin_color:
            colored = f"{plugin_color}{formatted}{Colors.RESET}"
        else:
            colored = f"{level_color}{formatted}{Colors.RESET}"

        return colored


class PluginLogger:
    """Logger wrapper for plugin communication logging."""

    def __init__(self, logger: logging.Logger, plugin_type: str):
        """
        Initialize plugin logger.

        Args:
            logger: Base logger
            plugin_type: Type of plugin (wikipedia, reranker, etc.)
        """
        self.logger = logger
        self.plugin_type = plugin_type

    def _log(self, level: int, msg: str, *args, **kwargs):
        """Log with plugin type extra."""
        extra = kwargs.get('extra', {})
        extra['plugin_type'] = self.plugin_type
        kwargs['extra'] = extra
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def setup_colored_logging(level: int = logging.INFO) -> None:
    """
    Setup colored logging for the application.

    Args:
        level: Logging level (default: INFO)
    """
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create colored formatter
    formatter = ColoredFormatter()
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add console handler
    root_logger.addHandler(console_handler)


def get_plugin_logger(name: str, plugin_type: str) -> PluginLogger:
    """
    Get a plugin logger with colored output.

    Args:
        name: Logger name (usually __name__)
        plugin_type: Type of plugin (wikipedia, reranker, classification, llm, etc.)

    Returns:
        PluginLogger instance
    """
    logger = logging.getLogger(name)
    return PluginLogger(logger, plugin_type)
