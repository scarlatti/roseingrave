"""
volunteer_summary.py
Export volunteer JSON data files.
"""

# ======================================================================

import click
from loguru import logger

from ._input_files import (
    read_piece_definitions,
    read_template,
    read_volunteer_definitions,
)
from ._output_files import read_spreadsheets_index, write_volunteer_data
from ._piece import Piece
from ._shared import error, fail_on_warning
from ._sheets import gspread_auth, open_spreadsheet

# ======================================================================

__all__ = ("volunteer_summary",)

# ======================================================================


def export_spreadsheet(gc, email, link, template, volunteer=None):
    """Export a volunteer's spreadsheet.

    Args:
        gc (gspread.Client): The client.
        email (str): The volunteer email.
        link (str): The spreadsheet link.
        template (Dict): The template settings.
        volunteer (Optional[Volunteer]): The volunteer. If given, only
            export the pieces belonging to this volunteer.
            Default is None.

    Returns:
        Tuple[bool, List[Dict]]: Whether the export was successful,
            and the exported data in JSON format.
    """
    ERROR_RETURN = False, None

    logger.debug('Working on volunteer "{}"', email)

    volunteer_pieces = None
    if volunteer is not None:
        volunteer_pieces = set(volunteer.pieces)

    success, spreadsheet = open_spreadsheet(gc, link)
    if not success:
        return ERROR_RETURN

    data = []
    for sheet in spreadsheet.worksheets():
        if volunteer_pieces is not None:
            if sheet.title not in volunteer_pieces:
                logger.warning(
                    'Volunteer "{}" does not have piece "{}" in piece '
                    "definitions file: skipping",
                    email,
                    sheet.title,
                )
                continue
        success, piece_data = Piece.export_sheet(sheet, template)
        if not success:
            continue
        data.append(piece_data)

    return True, data


# ======================================================================


@click.command(
    "volunteer_summary",
    help="Export volunteer JSON data files.",
)
@click.argument("emails", type=str, nargs=-1)
@click.option(
    "-si", type=str, help="A filepath to replace the spreadsheets index file."
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
    "-vdp",
    type=str,
    help=(
        "A filepath to replace the volunteer data path file. "
        'Must include "{email}".'
    ),
)
@click.option(
    "-ek",
    "--export-known-only",
    is_flag=True,
    default=False,
    flag_value=True,
    help=(
        "Export only the volunteers and pieces that appear in the "
        "definition files. Requires piece definitions file and "
        "volunteer definitions file. Default is False."
    ),
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Fail on warnings instead of only displaying them.",
)
def volunteer_summary(emails, si, td, pd, vd, vdp, export_known_only, strict):
    """Export volunteer JSON data files.

    Args:
        emails (Tuple[str, ...]): The volunteers to export data for. If
            none given, exports data for all volunteers.
        si (str): A filepath to replace the spreadsheets index file.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        vd (str): A filepath to replace the volunteer definitions file.
        vdp (str): A filepath to replace the volunteer data path file.
            Must include "{email}" exactly once.
        export_known_only (bool): Whether to export only the volunteers
            and pieces that appear in the definition files.
            Requires piece definitions file and volunteer definitions
            file.
            Default is False.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    # validate args
    if vdp is not None and vdp.count("{email}") != 1:
        error('`vdp` must include "{email}" exactly once')
        return

    success, gc = gspread_auth()
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si, must_exist=True)
    if not success:
        return
    # remove master spreadsheet
    spreadsheets.pop("MASTER", None)

    success, template = read_template(td, strict)
    if not success:
        return

    if len(emails) > 0:
        # filter volunteers in `emails`
        filtered = {}
        for email in emails:
            if email not in spreadsheets:
                logger.warning(
                    'Volunteer "{}" not found in spreadsheets index file',
                    email,
                )
                continue
            filtered[email] = spreadsheets[email]
        spreadsheets = filtered

    if len(spreadsheets) == 0:
        logger.info("No volunteers to export data for")
        return

    if export_known_only:
        success, pieces = read_piece_definitions(template, pd)
        if not success:
            return

        success, volunteers = read_volunteer_definitions(pieces, vd, strict)
        if not success:
            return
    else:
        volunteers = None

    # volunteer email -> data
    data = {}

    # export spreadsheets
    logger.info("Exporting data from spreadsheets")
    for email, link in spreadsheets.items():
        volunteer = None
        if volunteers is not None:
            if email not in volunteers:
                logger.warning(
                    'Unknown volunteer "{}": skipping spreadsheet', email
                )
                continue
            volunteer = volunteers[email]
        success, volunteer_data = export_spreadsheet(
            gc, email, link, template, volunteer
        )
        if strict and not success:
            fail_on_warning()
            return
        if success:
            data[email] = volunteer_data

    if len(data) > 0:
        success = write_volunteer_data(data, vdp)
        if not success:
            return

    logger.info("Done")
