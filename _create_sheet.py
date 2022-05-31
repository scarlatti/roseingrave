"""
_create_sheet.py
Create a volunteer spreadsheet.
"""

# ======================================================================

import click
import gspread.exceptions
from loguru import logger

from ._shared import fail_on_warning, error
from ._read_write import (
    read_definitions,
    read_spreadsheets_index, write_spreadsheets_index,
)
from ._sheets import (
    gspread_auth,
    open_spreadsheet,
    add_temp_sheet,
)

# ======================================================================

__all__ = ('create_sheet',)

# ======================================================================


def share(spreadsheet,
          email,
          role='reader',
          notify=False,
          msg=None
          ):
    """Share a spreadsheet with an email address.

    Args:
        spreadsheet (gspread.Spreadsheet): The spreadsheet.
        email (str): The email address.
        role (str): The role.
            Options are 'owner', 'writer', 'reader'.
            Default is 'reader'.
        notify (bool): Whether to notify the person.
            Default is False.
        msg (str): A message to send with the share notification.
            Default is None.

    Returns:
        bool: Whether the share was successful.
    """

    ERRORS = {
        400: {
            'invalid': (
                f'Invalid email "{email}"'
            ),
            'ownershipChangeAcrossDomainNotPermitted': (
                f'Invalid email "{email}": '
                'Ownership can only be transferred to another user '
                'in the same organization as the current owner.'
            ),
            'invalidSharingRequest': (
                f'Invalid email "{email}": '
                'No Google account associated with this email '
                'address.'
            ),
        },
        403: {
            'consentRequiredForOwnershipTransfer': (
                'Consent is required to transfer ownership of a '
                'file to another user.'
            ),
        },
    }

    role = role.strip().lower()
    if role not in ('owner', 'writer'):
        role = 'reader'

    try:
        spreadsheet.share(
            email,
            perm_type='user',
            role=role,
            notify=notify,
            email_message=msg
        )
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


# ======================================================================

def create_spreadsheets(gc, spreadsheets, owner, emails):
    """Create spreadsheets for the given volunteers.

    Args:
        gc (gspread.Client): The client.
        spreadsheets (Dict[str, str]): The existing spreadsheets.
        owner (str): The email of the owner.
        emails (Iterable[str]): The emails of the volunteers.

    Returns:
        bool: Whether the creations were successful.
    """

    if len(emails) == 0:
        return True

    logger.info('Creating new spreadsheets')

    created = []

    def delete_created():
        for ss in created:
            gc.del_spreadsheet(ss)

    for email in emails:
        spreadsheet = gc.create(email)
        created.append(spreadsheet.id)

        try:
            # make owner
            # FIXME: change role to "owner"
            success = share(spreadsheet, owner, 'writer')
            if not success:
                delete_created()
                return False

            # make volunteer an editor
            msg = (
                'This is an invitation for you to collaborate on a '
                'crowd-sourcing spreadsheet for a project run by '
                'Roseingrave. Thank you for accepting our invitation '
                'as a volunteer.'
            )
            success = share(spreadsheet, email, 'writer', True, msg)
            if not success:
                delete_created()
                return False
        except:
            delete_created()
            raise

        # make world-readable
        spreadsheet.share(None, perm_type='anyone', role='reader')

        spreadsheets[email] = spreadsheet.url

    return True

# ======================================================================


def populate_spreadsheets(gc, spreadsheets, volunteers, pieces, strict):
    """Populate the spreadsheets with the volunteer pieces.

    Args:
        gc (gspread.Client): The client.
        spreadsheets (Dict[str, str]): The spreadsheets.
        volunteers (Dict[str, Volunteer]): The volunteers.
        pieces (Dict[str, Piece]): The pieces.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        bool: Whether the population was successful.
    """

    logger.info('Populating spreadsheets with pieces')

    # piece name -> sheet object
    sheets = {}

    for email, volunteer in volunteers.items():
        logger.debug(f'Working on volunteer "{email}"')

        link = spreadsheets[email]
        success, spreadsheet = open_spreadsheet(gc, link)
        if not success:
            if strict:
                fail_on_warning()
                return False
            continue

        # delete existing sheets
        existing_sheets = list(spreadsheet.worksheets())
        invalid_temp_names = (
            set(volunteer.pieces) |
            set(sheet.title for sheet in existing_sheets)
        )
        success, temp_sheet = \
            add_temp_sheet(spreadsheet, invalid_temp_names)
        if not success:
            if strict:
                fail_on_warning()
                return False
            continue
        for sheet in existing_sheets:
            spreadsheet.del_worksheet(sheet)

        for piece_name in volunteer.pieces:
            if piece_name not in sheets:
                logger.debug(f'Creating sheet for piece "{piece_name}"')
                sheet = pieces[piece_name].create_sheet(spreadsheet)
                sheets[piece_name] = sheet
            else:
                # copy from previously created
                logger.debug(f'Copying sheet for piece "{piece_name}"')
                sheets[piece_name].copy_to(spreadsheet.id)

        # delete temp sheet
        spreadsheet.del_worksheet(temp_sheet)

    return True

# ======================================================================


@click.command(
    'create_sheet',
    help='Create volunteer spreadsheets.',
)
@click.argument('emails', type=str, nargs=-1)
@click.option(
    '-r', '--replace', is_flag=True, default=False, flag_value=True,
    help='Replace existing volunteer spreadsheets.'
)
@click.option(
    '-n', '--new', is_flag=True, default=False, flag_value=True,
    help='Create new spreadsheets for all volunteers.'
)
@click.option(
    '-td', type=str,
    help='A filepath to replace the template definitions file.'
)
@click.option(
    '-pd', type=str,
    help='A filepath to replace the piece definitions file.'
)
@click.option(
    '-vd', type=str,
    help='A filepath to replace the volunteer definitions file.'
)
@click.option(
    '-si', type=str,
    help='A filepath to replace the spreadsheets index file.'
)
@click.option(
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def create_sheet(emails, replace, new, td, pd, vd, si, strict):
    """Create volunteer spreadsheets.

    Args:
        emails (Tuple[str, ...]): The volunteers to create spreadsheets
            for. If none given, creates spreadsheets for all volunteers.
        replace (bool): Whether to replace existing volunteer
            spreadsheets.
            Default is False.
        new (bool): Whether to create new spreadsheets for all
            volunteers.
            Default is False.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        vd (str): A filepath to replace the volunteer definitions file.
        si (str): A filepath to replace the spreadsheets index file.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    success, gc = gspread_auth()
    if not success:
        return

    success, template, pieces, volunteers = \
        read_definitions(td, pd, vd, strict)
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si)
    if not success:
        return

    if len(emails) > 0:
        # filter volunteers in `emails`
        filtered = {}
        for email in emails:
            if email not in volunteers:
                logger.warning(
                    f'Volunteer "{email}" not found in volunteers '
                    'definitions file'
                )
                continue
            filtered[email] = volunteers[email]
        volunteers = filtered

    if new:
        # create new spreadsheets for all volunteers,
        # even if they already have a spreadsheet
        create_for = set(volunteers.keys())
    else:
        # don't create new for emails that already have a spreadsheet
        already_exist = {
            email for email in volunteers
            if email in spreadsheets
        }
        create_for = set(volunteers.keys()) - already_exist

        # if `replace` is false, don't edit existing spreadsheets
        if not replace:
            for email in already_exist:
                logger.debug(f'Volunteer "{email}" being skipped')
                volunteers.pop(email)

    if len(volunteers) == 0:
        logger.info('No volunteers to create spreadsheets for')
        return

    # create new spreadsheets
    success = create_spreadsheets(
        gc, spreadsheets, template['owner'], create_for
    )
    if not success:
        return

    # populate spreadsheets
    success = populate_spreadsheets(
        gc, spreadsheets, volunteers, pieces, strict
    )
    if not success:
        return

    if len(create_for) > 0:
        success = write_spreadsheets_index(spreadsheets, si)
        if not success:
            return

    logger.info('Done')
