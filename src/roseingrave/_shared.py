"""
_shared.py
Shared functions.
"""

# ======================================================================

from loguru import logger

# ======================================================================

__all__ = (
    'fail_on_warning',
    'error',
)

# ======================================================================


def fail_on_warning():
    """Display an error to fix all warnings."""
    logger.error('Please fix all errors and warnings and try again.')


def error(msg, return_value=None):
    """Display an error and return the provided return value."""
    logger.error(msg)
    return return_value
