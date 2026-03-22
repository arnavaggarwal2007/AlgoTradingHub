"""
================================================================================
STRUCTURED LOGGER FOR OPTIONS TRADING
================================================================================
Provides consistent logging across all strategies with:
- Console output (human-readable)
- JSON file logs (machine-parseable, audit trail)
- Separate audit log for trade executions
================================================================================
"""

import os
import logging
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger


class TradingJSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with trading context."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat() + 'Z'
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        log_record['function'] = record.funcName


def setup_logger(
    name: str = 'options_strategy',
    log_dir: str = 'logs',
    level: str = 'INFO',
) -> logging.Logger:
    """
    Set up structured logging for a strategy.
    
    Args:
        name: Logger name (e.g., 'wheel_strategy', 'spx_spreads')
        log_dir: Directory for log files
        level: Logging level
    
    Returns:
        Configured logger instance
    """
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(console)

    # JSON file handler
    json_handler = logging.FileHandler(
        os.path.join(log_dir, f'{name}.log')
    )
    json_handler.setFormatter(TradingJSONFormatter(
        '%(timestamp)s %(level)s %(module)s %(function)s %(message)s'
    ))
    logger.addHandler(json_handler)

    # Audit handler (WARNING+ only — trade executions, errors)
    audit_handler = logging.FileHandler(
        os.path.join(log_dir, f'{name}_audit.log')
    )
    audit_handler.setLevel(logging.WARNING)
    audit_handler.setFormatter(TradingJSONFormatter(
        '%(timestamp)s %(level)s %(module)s %(function)s %(message)s'
    ))
    logger.addHandler(audit_handler)

    return logger
