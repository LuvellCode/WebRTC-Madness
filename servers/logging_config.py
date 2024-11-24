import logging

# Кольори для логів
LOG_COLORS = {
    "DEBUG": "\033[94m",   # Blue
    "INFO": "\033[92m",    # Green
    "WARNING": "\033[93m", # Yellow
    "ERROR": "\033[91m",   # Red
    "CRITICAL": "\033[95m" # Violet
}
RESET_COLOR = "\033[0m"

# Formats
LOG_FORMAT = "[{asctime}] {level_color}{levelname:<8}{reset_color} {module:<15} {message}"
DATE_FORMAT = "%d.%m.%Y %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(fmt=LOG_FORMAT, style="{", datefmt=DATE_FORMAT)

    def format(self, record):
        log_color = LOG_COLORS.get(record.levelname, RESET_COLOR)
        record.level_color = log_color
        record.reset_color = RESET_COLOR
        return super().format(record)


def get_logger(name=None, level=logging.INFO):
    """
    Returns a set up logger with coloring
    
    :param name: usually __name__.
    :param level: (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logger = logging.getLogger(name)
    if not logger.handlers:  # Duplication check
        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger