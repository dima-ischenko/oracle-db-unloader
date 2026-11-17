from __future__ import annotations

import io
import logging

import pytest

from oracle_db_unloader.logger import (
    PACKAGE_LOGGER_NAME,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def reset_package_logger():
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    handlers = list(logger.handlers)
    level = logger.level
    propagate = logger.propagate
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_import_does_not_attach_stream_handler():
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    assert not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.NullHandler)
        for handler in logger.handlers
    )


def test_configure_logging_writes_format():
    stream = io.StringIO()
    configure_logging('INFO', stream=stream)
    get_logger('oracle_db_unloader.unloader').info('hello-unload')
    rendered = stream.getvalue()
    assert 'oracle_db_unloader.unloader' in rendered
    assert 'hello-unload' in rendered


def test_configure_logging_is_idempotent():
    stream = io.StringIO()
    configure_logging('INFO', stream=stream)
    configure_logging('DEBUG', stream=stream)
    cli_handlers = [
        handler
        for handler in logging.getLogger(PACKAGE_LOGGER_NAME).handlers
        if handler.get_name() == 'oracle_db_unloader.cli'
    ]
    assert len(cli_handlers) == 1


def test_unknown_log_level_raises():
    with pytest.raises(ValueError, match='unknown log level'):
        configure_logging('NOPE')
