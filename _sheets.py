"""
_sheets.py
Shared methods for interacting with spreadsheets.
"""

# ======================================================================

import gspread.exceptions
from loguru import logger

from ._shared import error
from ._read_write import (
    _read_settings,
    _get_path,
)

# ======================================================================

__all__ = (
    'gspread_auth',
    'open_spreadsheet',
    'add_temp_sheet',
)

# ======================================================================


def gspread_auth(force=False):
    """Authenticate gspread to connect with Google Sheets.

    Args:
        force (bool): Whether to force the authentication.
            Default is False.

    Returns:
        Tuple[bool, gspread.Client]: Whether the setup was successful,
            and the client.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Setting up gspread authentication')
    try:
        filepath = _get_path('credentials')
    except FileNotFoundError as ex:
        return _error(ex)

    auth_user_path = _get_path('authorized_user', must_exist=False)
    # use `.resolve()` to turn this into the full path to avoid this:
    # https://github.com/burnash/gspread/issues/1056
    auth_user_path = auth_user_path.resolve()

    if force and auth_user_path.exists():
        auth_user_path.unlink()

    try:
        client = gspread.oauth(
            credentials_filename=str(filepath),
            authorized_user_filename=str(auth_user_path),
            flow=gspread.auth.console_flow
        )
    except Exception as ex:
        # incorrect authorization code
        return _error(ex)

    return True, client

# ======================================================================


def open_spreadsheet(gc, link):
    """Open a spreadsheet.

    Args:
        gc (gspread.Client): The client.
        link (str): The link of the spreadsheet to open.

    Returns:
        Tuple[bool, gspread.Spreadsheet]:
            Whether the open was successful, and the spreadsheet.
    """

    ERRORS = {
        403: {
            'PERMISSION_DENIED': (
                f'Couldn\'t open spreadsheet "{link}" (permission '
                'denied). Please make sure this spreadsheet is shared '
                'with the you, or remove it from the spreadsheets '
                'index file.'
            ),
        },
        404: {
            'NOT_FOUND': (
                f'Couldn\'t open spreadsheet "{link}" (not found). '
                'Please remove it from the spreadsheets index file.'
            ),
        },
    }

    try:
        return True, gc.open_by_url(link)
    except gspread.exceptions.APIError as ex:
        args = ex.args[0]

        code = args['code']
        status = args['status']

        try:
            logger.warning(ERRORS[code][status])
            return False, None
        except KeyError:
            pass

        # re-raise
        raise

# ======================================================================


def add_temp_sheet(spreadsheet, invalid=None):
    """Add a temp sheet to a spreadsheet.

    Args:
        spreadsheet (gspread.Spreadsheet): The spreadsheet.
        invalid (Set[str]): A set of invalid names.
            Default is None.

    Returns:
        Tuple[bool, gspread.Worksheet]:
            Whether the addition was successful, and the temp sheet.
    """

    ERRORS = {
        403: {
            'PERMISSION_DENIED': (
                f'Couldn\'t edit spreadsheet "{spreadsheet.url}". '
                'Please make sure this spreadsheet is shared with you '
                'with edit permissions, or remove it from the '
                'spreadsheets index file.'
            ),
        },
    }

    if invalid is None:
        invalid = set()

    title = '_temp'
    count = 0
    while title in invalid:
        count += 1
        title = f'_temp{count}'

    try:
        return True, spreadsheet.add_worksheet(title, 1, 1)
    except gspread.exceptions.APIError as ex:
        args = ex.args[0]

        code = args['code']
        status = args['status']

        try:
            logger.warning(ERRORS[code][status])
            return False, None
        except KeyError:
            pass

        # re-raise
        raise
