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
    logger.error('Please fix all warnings and try again.')


def error(msg, return_value=None):
    logger.error(msg)
    return return_value
