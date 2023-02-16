"""
create_sheet.py
Create a volunteer spreadsheet.
"""

# ======================================================================

import click
from loguru import logger

from ._input_files import (
    read_piece_definitions,
    read_template,
    read_volunteer_definitions,
)
from ._output_files import read_spreadsheets_index, write_spreadsheets_index
from ._shared import fail_on_warning
from ._sheets import (
    add_permissions,
    add_temp_sheet,
    create_spreadsheet,
    gspread_auth,
    open_spreadsheet,
    share_spreadsheet,
)

# ======================================================================

__all__ = ("create_sheet",)

# ======================================================================

INVITATION_MESSAGE = (
    "This is an invitation for you to collaborate on a crowd-sourcing "
    "spreadsheet for a project run by Roseingrave. Thank you for accepting "
    "our invitation as a volunteer."
)

# ======================================================================


class VolunteerSpreadsheet:
    """Represents a volunteer's spreadsheet."""

    def __init__(self, volunteer, url=None, extend=False):
        self._volunteer = volunteer
        self._url = url
        self._spreadsheet = None
        # If False, the spreadsheet will be wiped first
        self._extend_spreadsheet = extend

    @property
    def volunteer(self):
        return self._volunteer

    @property
    def extend_spreadsheet(self):
        return self._extend_spreadsheet

    def add_created_spreadsheet(self, spreadsheet):
        """Adds the given spreadsheet for this volunteer."""
        self._url = spreadsheet.url
        self._spreadsheet = spreadsheet

    def get_spreadsheet(self, gc):
        """Gets this volunteer's spreadsheet, opening it if necessary."""
        if self._spreadsheet is None:
            if self._url is None:
                raise RuntimeError(
                    "missing spreadsheet url for volunteer "
                    f'"{self._volunteer.email}"'
                )
            success, spreadsheet = open_spreadsheet(gc, self._url)
            if not success:
                return success, None
            self._spreadsheet = spreadsheet
        return True, self._spreadsheet


# ======================================================================


def create_spreadsheets(
    gc, spreadsheets, volunteer_spreadsheets, template, emails
):
    """Create spreadsheets for the given volunteers.

    Args:
        gc (gspread.Client): The client.
        spreadsheets (Dict[str, str]): The existing spreadsheet urls.
        volunteer_spreadsheets (Dict[str, VolunteerSpreadsheet]):
            The VolunteerSpreadsheet objects for each volunteer.
        template (Dict): The template settings.
        emails (Iterable[str]): The emails of the volunteers to create
            spreadsheets for.

    Returns:
        bool: Whether the creations were successful.
    """

    if len(emails) == 0:
        return True

    logger.info("Creating new spreadsheets")

    created = []

    def delete_created():
        for ss in created:
            gc.del_spreadsheet(ss)

    ss_settings = template["volunteerSpreadsheet"]
    folder = ss_settings["folder"]
    title_fmt = ss_settings["title"]
    public_access = ss_settings["publicAccess"]
    share_with_volunteer = ss_settings["shareWithVolunteer"]
    share_with = ss_settings["shareWith"]

    for email in emails:
        success, spreadsheet = create_spreadsheet(
            gc, title_fmt.format(email=email), folder
        )
        if not success:
            delete_created()
            return False
        created.append(spreadsheet.id)

        success = add_permissions(spreadsheet, public_access, share_with)
        if not success:
            delete_created()
            return False

        if share_with_volunteer:
            # make volunteer an editor
            success = share_spreadsheet(
                spreadsheet, email, "edit", notify=True, msg=INVITATION_MESSAGE
            )
            if not success:
                delete_created()
                return False

        spreadsheets[email] = spreadsheet.url
        volunteer_spreadsheets[email].add_created_spreadsheet(spreadsheet)

    return True


# ======================================================================


def populate_spreadsheets(gc, volunteer_spreadsheets, pieces, strict):
    """Populate the spreadsheets with the volunteer pieces.

    Args:
        gc (gspread.Client): The client.
        volunteer_spreadsheets (Dict[str, VolunteerSpreadsheet]):
            The VolunteerSpreadsheet objects for each volunteer.
        pieces (Dict[str, Piece]): The pieces.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        bool: Whether the population was successful.
    """

    logger.info("Populating spreadsheets with pieces")

    # piece name -> sheet object
    sheets = {}

    for email, volunteer_spreadsheet in volunteer_spreadsheets.items():
        logger.debug('Working on volunteer "{}"', email)
        volunteer = volunteer_spreadsheet.volunteer

        success, spreadsheet = volunteer_spreadsheet.get_spreadsheet(gc)
        if not success:
            if strict:
                fail_on_warning()
                return False
            continue

        existing_sheets = {
            sheet.title: sheet for sheet in spreadsheet.worksheets()
        }
        temp_sheet = None

        sheet_names_set = set(existing_sheets.keys())
        piece_names_set = set(volunteer.pieces)
        if volunteer_spreadsheet.extend_spreadsheet:
            # extend the sheet: only create the missing pieces
            # check for extra sheets that don't match the piece names
            extra_sheets = sheet_names_set - piece_names_set
            if len(extra_sheets) > 0:
                logger.warning(
                    "Found extra piece sheets: {}",
                    ",".join(f'"{sheet_name}"' for sheet_name in extra_sheets),
                )
                if strict:
                    fail_on_warning()
                    return False
        else:
            # delete existing sheets
            if len(existing_sheets) == 1:
                # no need to add temp sheet: use the only sheet
                _, temp_sheet = existing_sheets.popitem()
            else:
                # add a temp sheet
                invalid_names = piece_names_set | sheet_names_set
                success, temp_sheet = add_temp_sheet(
                    spreadsheet, invalid_names
                )
                if not success:
                    if strict:
                        fail_on_warning()
                        return False
                    continue
                for sheet in existing_sheets.values():
                    spreadsheet.del_worksheet(sheet)
            existing_sheets.clear()

        # create the piece sheets
        worksheets_in_piece_order = []
        for piece_name in volunteer.pieces:
            if piece_name in existing_sheets:
                worksheets_in_piece_order.append(existing_sheets[piece_name])
                logger.debug(
                    'Skipping piece "{}": already exists in sheet', piece_name
                )
                continue
            if piece_name not in sheets:
                logger.debug('Creating sheet for piece "{}"', piece_name)
                sheet = pieces[piece_name].create_sheet(spreadsheet)
                sheets[piece_name] = sheet
            else:
                # copy from previously created
                logger.debug('Copying sheet for piece "{}"', piece_name)
                data = sheets[piece_name].copy_to(spreadsheet.id)
                # update sheet title to piece name
                sheet = spreadsheet.get_worksheet_by_id(data["sheetId"])
                sheet.update_title(piece_name)
            worksheets_in_piece_order.append(sheet)

        # delete temp sheet
        if temp_sheet is not None:
            spreadsheet.del_worksheet(temp_sheet)

        # reorder sheets according to piece order
        spreadsheet.reorder_worksheets(worksheets_in_piece_order)

    return True


# ======================================================================


@click.command(
    "create_sheet",
    help="Create volunteer spreadsheets.",
)
@click.argument("emails", type=str, nargs=-1)
@click.option(
    "-e",
    "--extend",
    is_flag=True,
    default=False,
    flag_value=True,
    help=(
        "Extend existing sheets with missing pieces. "
        "Cannot be set when `--replace` or `--new` is set."
    ),
)
@click.option(
    "-r",
    "--replace",
    is_flag=True,
    default=False,
    flag_value=True,
    help=(
        "Wipe and replace existing volunteer spreadsheets. "
        "Cannot be set when `--extend` is set. "
        "Has no effect when `--new` is set."
    ),
)
@click.option(
    "-n",
    "--new",
    is_flag=True,
    default=False,
    flag_value=True,
    help=(
        "Create new spreadsheets for all volunteers. "
        "Cannot be set when `--extend` is set."
    ),
)
@click.option(
    "-td",
    type=str,
    help="A filepath to replace the template definitions file.",
)
@click.option(
    "-pd", type=str, help="A filepath to replace the piece definitions file."
)
@click.option(
    "-vd",
    type=str,
    help="A filepath to replace the volunteer definitions file.",
)
@click.option(
    "-si", type=str, help="A filepath to replace the spreadsheets index file."
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Fail on warnings instead of only displaying them.",
)
def create_sheet(emails, extend, replace, new, td, pd, vd, si, strict):
    """Create volunteer spreadsheets.

    Args:
        emails (Tuple[str, ...]): The volunteers to create spreadsheets
            for. If none given, creates spreadsheets for all volunteers.
        extend (bool): Whether to extend existing sheets with missing
            pieces. New sheets will still be created.
            Cannot be True when `replace` or `new` is True.
            Default is False.
        replace (bool): Whether to wipe and replace existing volunteer
            spreadsheets.
            Cannot be True when `extend` is True.
            Has no effect when `new` is True.
            Default is False.
        new (bool): Whether to create new spreadsheets for all
            volunteers.
            Cannot be True when `extend` is True.
            Default is False.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        vd (str): A filepath to replace the volunteer definitions file.
        si (str): A filepath to replace the spreadsheets index file.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """
    if extend and (replace or new):
        logger.error("`extend` can only be True on its own")
        return
    if replace and new:
        logger.warning("`--replace` has no effect since `--new` is set")

    success, gc = gspread_auth()
    if not success:
        return

    success, template = read_template(td, strict)
    if not success:
        return

    success, pieces = read_piece_definitions(template, pd)
    if not success:
        return

    success, volunteers = read_volunteer_definitions(pieces, vd, strict)
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si)
    if not success:
        return

    if len(emails) > 0:
        # filter volunteers in `emails`
        filtered = {}
        email_not_found = False
        for email in emails:
            # don't allow this to update the master spreadsheet
            # this technically won't change the actual behavior, since
            # there is no "MASTER" volunteer email
            if email == "MASTER":
                continue
            if email not in volunteers:
                email_not_found = True
                logger.warning(
                    'Volunteer "{}" not found in volunteer definitions file',
                    email,
                )
                continue
            filtered[email] = volunteers[email]
        if strict and email_not_found:
            fail_on_warning()
            return
        volunteers = filtered

    if new:
        # create new spreadsheets for all volunteers, even if they
        # already have a spreadsheet
        create_for = set(volunteers.keys())
    else:
        # don't create new for emails that already have a spreadsheet
        already_exist = {
            email for email in volunteers if email in spreadsheets
        }
        create_for = set(volunteers.keys()) - already_exist

        if extend or replace:
            # process the existing spreadsheets
            pass
        else:
            # remove existing spreadsheets: don't edit them
            for email in already_exist:
                logger.debug(
                    'Skipping volunteer "{}": '
                    "already in spreadsheets index file",
                    email,
                )
                volunteers.pop(email)

    if len(volunteers) == 0:
        logger.info("No volunteers to create spreadsheets for")
        return

    volunteer_spreadsheets = {}
    for email, volunteer in volunteers.items():
        if email in spreadsheets:
            # volunteer has existing spreadsheet
            url = spreadsheets[email]
            extend_spreadsheet = extend
        else:
            url = None
            extend_spreadsheet = False
        volunteer_spreadsheets[email] = VolunteerSpreadsheet(
            volunteer, url=url, extend=extend_spreadsheet
        )

    # create new spreadsheets
    success = create_spreadsheets(
        gc, spreadsheets, volunteer_spreadsheets, template, create_for
    )
    if not success:
        return

    # populate spreadsheets
    success = populate_spreadsheets(gc, volunteer_spreadsheets, pieces, strict)
    if not success:
        return

    if len(create_for) > 0:
        success = write_spreadsheets_index(spreadsheets, si)
        if not success:
            return

    logger.info("Done")
