from __future__ import annotations

import logging
import sys
from typing import Optional, TextIO, Union

PACKAGE_LOGGER_NAME = 'oracle_db_unloader'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s.%(funcName)s - %(message)s'
_CLI_HANDLER_NAME = 'oracle_db_unloader.cli'

_package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
if not any(
    isinstance(handler, logging.NullHandler) for handler in _package_logger.handlers
):
    _package_logger.addHandler(logging.NullHandler())


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if name is None or name == PACKAGE_LOGGER_NAME:
        return logging.getLogger(PACKAGE_LOGGER_NAME)
    if name.startswith(PACKAGE_LOGGER_NAME + '.'):
        return logging.getLogger(name)
    return logging.getLogger(f'{PACKAGE_LOGGER_NAME}.{name}')


def configure_logging(
    level: Union[int, str] = logging.INFO,
    *,
    stream: Optional[TextIO] = None,
) -> logging.Logger:
    """Attach a stderr handler for CLI use. Safe to call more than once.

    Library imports do not configure handlers; the host process owns that.
    """
    if isinstance(level, str):
        numeric = logging.getLevelName(level.upper())
        if not isinstance(numeric, int):
            raise ValueError(f'unknown log level: {level}')
        level = numeric

    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    existing = next(
        (handler for handler in logger.handlers if handler.get_name() == _CLI_HANDLER_NAME),
        None,
    )
    if existing is not None:
        existing.setLevel(level)
        if stream is not None:
            existing.stream = stream
        return logger

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.set_name(_CLI_HANDLER_NAME)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    return logger
