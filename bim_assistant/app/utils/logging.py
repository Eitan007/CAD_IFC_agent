"""app/utils/logging.py"""
import logging
import structlog


def configure_logging(level: str = "INFO"):
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
    )
