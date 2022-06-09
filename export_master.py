"""
export_master.py
Export the master spreadsheet.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import error
from ._input_files import (
    read_template,
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

__all__ = ('export_master',)

# ======================================================================

MASTER_KEY = 'MASTER'

# ======================================================================


@click.command(
    'export_master',
    help='Export the master spreadsheet.'
)
@click.option(
    '-si', type=str,
    help='A filepath to replace the spreadsheets index file.'
)
@click.option(
    '-td', type=str,
    help='A filepath to replace the template definitions file.'
)
@click.option(
    '-s', 'summary_path', type=str,
    help='A filepath to replace the summary file.'
)
@click.option(
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def export_master(si, td, summary_path, strict):
    """Export the master spreadsheet.

    Args:
        si (str): A filepath to replace the spreadsheets index file.
        td (str): A filepath to replace the template definitions file.
        summary_path (str): A filepath to replace the summary file.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    success, gc = gspread_auth()
    if not success:
        return

    success, spreadsheets = read_spreadsheets_index(si)
    if not success:
        return

    if MASTER_KEY not in spreadsheets:
        error(
            f'Master spreadsheet (key "{MASTER_KEY}") not found in '
            'spreadsheets index file'
        )
        return

    success, template = read_template(td, strict)
    if not success:
        return

    success, spreadsheet = open_spreadsheet(
        gc, spreadsheets[MASTER_KEY]
    )
    if not success:
        return

    summary = []
    for sheet in spreadsheet.worksheets():
        success, piece_data = Piece.export_master_sheet(
            sheet, template
        )
        if not success:
            return
        summary.append(piece_data)

    success = write_summary(summary, summary_path)
    if not success:
        return

    logger.info('Done')
