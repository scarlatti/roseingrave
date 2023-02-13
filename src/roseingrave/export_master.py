"""
export_master.py
Export the master spreadsheet.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import fail_on_warning, error
from ._input_files import (
    read_template,
    read_piece_definitions,
    read_volunteer_definitions,
)
from ._output_files import (
    read_spreadsheets_index,
    write_summary,
)
from ._sheets import (
    gspread_auth,
    open_spreadsheet,
)
from ._piece import Piece

# ======================================================================

__all__ = ("export_master",)

# ======================================================================

MASTER_KEY = "MASTER"

# ======================================================================


def filter_volunteers(piece_name, piece_volunteers, piece_data):
    removed = set()

    def remove_volunteers(obj):
        for volunteer in list(obj.keys()):
            if volunteer in piece_volunteers:
                continue
            if volunteer not in removed:
                # only log warning once per unknown volunteer
                logger.warning(
                    'Unknown volunteer "{}" for piece "{}" (not in '
                    "volunteer definitions file)",
                    volunteer,
                    piece_name,
                )
                removed.add(volunteer)
            obj.pop(volunteer)

    # remove from sources
    for source in piece_data["sources"]:
        remove_volunteers(source["volunteers"])
        # can't do anything about "summary", since that's inputted from
        # the master user
    # remove from notes
    for key, volunteer_data in piece_data["notes"].items():
        if key == "bars":
            # special case: bars
            for bar_data in volunteer_data.values():
                remove_volunteers(bar_data)
        else:
            remove_volunteers(volunteer_data)


# ======================================================================


@click.command("export_master", help="Export the master spreadsheet.")
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
    "-s",
    "summary_path",
    type=str,
    help="A filepath to replace the summary file.",
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
def export_master(si, td, pd, vd, summary_path, export_known_only, strict):
    """Export the master spreadsheet.

    Args:
        si (str): A filepath to replace the spreadsheets index file.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        vd (str): A filepath to replace the volunteer definitions file.
        summary_path (str): A filepath to replace the summary file.
        export_known_only (bool): Whether to export only the volunteers
            and pieces that appear in the definition files.
            Requires piece definitions file and volunteer definitions
            file.
            Default is False.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    success, gc = gspread_auth()
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si, must_exist=True)
    if not success:
        return

    if MASTER_KEY not in spreadsheets:
        error(
            f'Master spreadsheet (key "{MASTER_KEY}") not found in '
            "spreadsheets index file"
        )
        return

    success, template = read_template(td, strict)
    if not success:
        return

    if export_known_only:
        success, pieces = read_piece_definitions(template, pd)
        if not success:
            return

        success, volunteers = read_volunteer_definitions(pieces, vd, strict)
        if not success:
            return

        piece_volunteers = {piece_name: set() for piece_name in pieces.keys()}
        for email, volunteer in volunteers.items():
            # the volunteer's pieces definitely exist
            for piece_name in volunteer.pieces:
                piece_volunteers[piece_name].add(email)
    else:
        piece_volunteers = None

    success, spreadsheet = open_spreadsheet(gc, spreadsheets[MASTER_KEY])
    if not success:
        return

    summary = []
    for sheet in spreadsheet.worksheets():
        if piece_volunteers is not None:
            if sheet.title not in piece_volunteers:
                logger.warning(
                    'Unknown piece "{}" (not in piece definitions '
                    "file: skipping sheet",
                    sheet.title,
                )
                continue
        success, piece_data = Piece.export_master_sheet(sheet, template)
        if not success:
            if strict:
                fail_on_warning()
                return
            continue
        if piece_volunteers is not None:
            filter_volunteers(
                sheet.title, piece_volunteers[sheet.title], piece_data
            )
        summary.append(piece_data)

    if len(summary) > 0:
        success = write_summary(summary, summary_path)
        if not success:
            return

    logger.info("Done")
