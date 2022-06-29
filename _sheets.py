"""
_sheets.py
Shared methods for interacting with spreadsheets.
"""
# Need to access error data, but pylint complains
# Logs all unexpected exceptions
# pylint: disable=invalid-sequence-index,broad-except

# ======================================================================

import google.auth.exceptions
import gspread.exceptions
from loguru import logger

from ._shared import error
from ._read_write import (
    get_path,
    read_settings,
)

# ======================================================================

__all__ = (
    'gspread_auth',
    'create_spreadsheet',
    'open_spreadsheet',
    'add_temp_sheet',
    'share_spreadsheet', 'share_public',
    'add_permissions',
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

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Setting up gspread authentication')
    try:
        filepath = get_path('credentials')
    except FileNotFoundError as ex:
        return _error(ex)

    auth_user_path = get_path('authorized_user', must_exist=False)
    # use `.resolve()` to turn this into the full path to avoid this:
    # https://github.com/burnash/gspread/issues/1056
    auth_user_path = auth_user_path.resolve()

    if force and auth_user_path.exists():
        auth_user_path.unlink()

    oauth_args = {
        'credentials_filename': str(filepath),
        'authorized_user_filename': str(auth_user_path),
        'flow': gspread.auth.console_flow,
    }
    try:
        client = gspread.oauth(**oauth_args)
    except Exception as ex:
        # incorrect authorization code
        return _error(ex)

    # check if the OAuth Client is expired
    try:
        client.list_spreadsheet_files()
    except google.auth.exceptions.RefreshError:
        logger.warning('OAuth client credentials expired; refreshing')
        auth_user_path.unlink()
        # try again
        try:
            client = gspread.oauth(**oauth_args)
        except Exception as ex:
            # incorrect authorization code
            return _error(ex)

    return True, client

# ======================================================================


def create_spreadsheet(gc, name, folder=None):
    """Create a spreadsheet.

    Args:
        gc (gspread.Client): The client.
        name (str): The name of the spreadsheet.
        folder (Optional[str]): The id of the Google Drive folder to
            save the spreadsheet in.
            Default is None (save in root).

    Returns:
        Tuple[bool, gspread.Spreadsheet]:
            Whether the creation was successful, and the spreadsheet.
    """

    # code -> error reason -> message
    ERRORS = {
        404: {
            'notFound': (
                f'Couldn\'t find folder "{folder}". '
                'Please check that it\'s correct or remove it.'
            ),
        },
    }

    try:
        return True, gc.create(name, folder)
    except gspread.exceptions.APIError as ex:
        args = ex.args[0]

        code = args['code']
        if code in ERRORS:
            for err in args['errors']:
                reason = err['reason']
                if reason in ERRORS[code]:
                    error(ERRORS[code][reason])
                    return False, None

        # re-raise
        raise

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

    # code -> status -> message
    ERRORS = {
        403: {
            'PERMISSION_DENIED': (
                f'Couldn\'t open spreadsheet "{link}" (permission '
                'denied). Please make sure this spreadsheet is shared '
                'with you, or remove it from the spreadsheets '
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
    except gspread.exceptions.NoValidUrlKeyFound:
        error(f'Invalid spreadsheet link: "{link}"')
        return False, None
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

    # code -> status -> message
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

# ======================================================================


def _access_to_role(access, default):
    access = access.strip().lower()
    role = default
    if access == 'view':
        role = 'reader'
    elif access == 'edit':
        role = 'writer'
    return role


def _share(spreadsheet, email, *args, **kwargs):
    """Share a spreadsheet. Return True if successful."""

    # code -> error reason -> message
    ERRORS = {
        400: {
            'invalid': (
                f'Invalid email "{email}"'
            ),
            'invalidSharingRequest': (
                # only happens if notify=False
                f'Invalid email "{email}": '
                'No Google account associated with this email address.'
            ),
        },
        403: {
            'forbidden': (
                'Insufficient permissions to share spreadsheet '
                f'"{spreadsheet.title}".'
            )
        },
    }

    try:
        spreadsheet.share(email, *args, **kwargs)
        return True
    except gspread.exceptions.APIError as ex:
        args = ex.args[0]

        code = args['code']
        if code in ERRORS:
            for err in args['errors']:
                reason = err['reason']
                if reason in ERRORS[code]:
                    error(ERRORS[code][reason])
                    return False

        # re-raise
        raise


def share_spreadsheet(spreadsheet,
                      email,
                      access='view',
                      notify=False,
                      msg=None
                      ):
    """Share a spreadsheet with an email address.

    Args:
        spreadsheet (gspread.Spreadsheet): The spreadsheet.
        email (str): The email address.
        access (str): The access level.
            Options are "view" and "edit".
            Default is "view".
        notify (bool): Whether to notify the person.
            Default is False.
        msg (str): A message to send with the share notification.
            Default is None.

    Returns:
        bool: Whether the share was successful.
    """

    role = _access_to_role(access, 'reader')

    success = _share(
        spreadsheet,
        email,
        perm_type='user',
        role=role,
        notify=notify,
        email_message=msg
    )
    return success


def share_public(spreadsheet, access=None):
    """Share a spreadsheet publicly.
    Assumes the spreadsheet is not currently shared publicly.
    (That is, cannot restrict spreadsheet access; can only share.)

    Args:
        spreadsheet (gspread.Spreadsheet): The spreadsheet.
        access (Optional[str]): The access level.
            Choices are None, "view", and "edit".
            Default is None.

    Returns:
        bool: Whether the share was successful.
    """

    if access is None:
        return True

    role = _access_to_role(access, None)

    # don't share
    if role is None:
        return True

    success = _share(spreadsheet, None, perm_type='anyone', role=role)
    return success


def add_permissions(spreadsheet, public_access=None, share_with=None):
    """Add permissions to spreadsheet.

    Args:
        spreadsheet (gspread.Spreadsheet): The spreadsheet.
        public_access (Optional[str]): The public access level.
            Options are None, "view", and "edit".
            Default is None.
        share_with (List[str]): Email addresses to give edit access to.
            Default is None.

    Returns:
        bool: Whether the shares are successful.
    """
    if share_with is None:
        share_with = []

    try:
        success = share_public(spreadsheet, public_access)
        if not success:
            return False

        for email in share_with:
            success = share_spreadsheet(spreadsheet, email, 'edit')
            if not success:
                return False
    except Exception as ex:
        error(ex)
        return False

    return True
