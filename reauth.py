"""
reauth.py
Reauthenticate the credentials for your OAuth Client.
"""

# ======================================================================

import click
from loguru import logger

from ._sheets import gspread_auth

# ======================================================================

__all__ = ('reauth',)

# ======================================================================


@click.command(
    'reauth',
    help='Reauthenticate the credentials for your OAuth Client.'
)
def reauth():
    success, _ = gspread_auth(force=True)
    if not success:
        return

    logger.info('Done')
