import logging


class BetterLog:
    def __init__(self, logger: logging.Logger, log_prefix:str = None):
        self.log_prefix = log_prefix if log_prefix is not None else self.__class__.__name__
        self.logger = logger

    def log(self, level, message):
        formatted_message = f"[{self.log_prefix}] {message}"
        self.logger.log(level=level, msg=formatted_message)
    
    def log_debug(self, message):
        self.log(logging.DEBUG, message)
    
    def log_info(self, message):
        self.log(logging.INFO, message)
    
    def log_warn(self, message):
        self.log(logging.WARN, message)
    
    def log_error(self, message):
        self.log(logging.ERROR, message)
