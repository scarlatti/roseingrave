"""
import_summary.py
Update the summary spreadsheet.
"""

# ======================================================================

import click
from loguru import logger

from ._input_files import read_piece_definitions, read_template
from ._output_files import (
    SI_SUMMARY_KEY,
    read_spreadsheets_index,
    read_summary,
    write_spreadsheets_index,
)
from ._sheets import (
    add_permissions,
    add_temp_sheet,
    create_spreadsheet,
    gspread_auth,
    open_spreadsheet,
)

# ======================================================================

__all__ = ("import_summary",)

# ======================================================================


def _create_piece_sheets(spreadsheet, pieces, summary):
    """Create the piece sheets in the summary spreadsheet.

    Args:
        spreadsheet (gspread.Spreadsheet): The summary spreadsheet.
        pieces (Dict[str, Piece]): A mapping from piece names to piece
            objects.
        summary (Dict[str, Dict]): The piece summary.

    Returns:
        bool: Whether the creations were successful.
    """

    # delete existing sheets
    existing_sheets = list(spreadsheet.worksheets())
    success, temp_sheet = add_temp_sheet(spreadsheet, invalid=summary.keys())
    if not success:
        return False
    for sheet in existing_sheets:
        spreadsheet.del_worksheet(sheet)

    for title in summary.keys():
        logger.debug('Creating sheet for piece "{}"', title)
        pieces[title].create_summary_sheet(spreadsheet, summary[title])

    # delete temp sheet
    spreadsheet.del_worksheet(temp_sheet)

    return True


# ======================================================================


@click.command("import_summary", help="Update the summary spreadsheet.")
@click.option(
    "-c",
    "--create",
    is_flag=True,
    default=False,
    flag_value=True,
    help="Create a new summary spreadsheet.",
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
    "-s",
    "summary_path",
    type=str,
    help="A filepath to replace the summary file.",
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
def import_summary(create, td, pd, summary_path, si, strict):
    """Update the summary spreadsheet.

    Args:
        create (str): Whether to create a new summary spreadsheet.
            Default is False.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        summary_path (str): A filepath to replace the summary file.
        si (str): A filepath to replace the spreadsheets index file.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    logger.warning(
        "For most accurate summary, run the `compile_pieces` or "
        "`export_summary` command first."
    )

    success, gc = gspread_auth()
    if not success:
        return

    success, template = read_template(td, strict)
    if not success:
        return

    success, (pieces, pieces_data) = read_piece_definitions(
        template, pd, as_both=True
    )
    if not success:
        return

    success, summary = read_summary(pieces_data, summary_path, strict)
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si)
    if not success:
        return

    # check if need to create spreadsheet
    if SI_SUMMARY_KEY not in spreadsheets:
        logger.debug(
            "Summary spreadsheet link not found in spreadsheets index "
            "file: creating new"
        )
        create = True

    # create or open spreadsheet
    if create:
        ss_settings = template["summarySpreadsheet"]

        success, spreadsheet = create_spreadsheet(
            gc, ss_settings["title"], ss_settings["folder"]
        )
        if not success:
            return

        # permissions
        success = add_permissions(
            spreadsheet, ss_settings["publicAccess"], ss_settings["shareWith"]
        )
        if not success:
            gc.del_spreadsheet(spreadsheet.id)
            return

        # save link
        spreadsheets[SI_SUMMARY_KEY] = spreadsheet.url
    else:
        link = spreadsheets[SI_SUMMARY_KEY]
        success, spreadsheet = open_spreadsheet(gc, link)
        if not success:
            return

    # create pieces
    success = _create_piece_sheets(spreadsheet, pieces, summary)
    if create and not success:
        # delete created spreadsheet
        gc.del_spreadsheet(spreadsheet.id)
        return

    if create:
        success = write_spreadsheets_index(spreadsheets, si)
        if not success:
            return

    logger.info("Done")
