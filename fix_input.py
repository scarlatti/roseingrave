"""
fix_input.py
Fixes input files.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import error
from ._read_write import (
    fix_settings,
)
from ._input_files import (
    read_template,
    read_piece_definitions, fix_piece_definitions,
    fix_volunteer_definitions,
)
from ._output_files import (
    fix_spreadsheets_index,
)

# ======================================================================

__all__ = ('fix_input',)

# ======================================================================

FILES = {
    key: True for key in (
        'settings',
        'pieces',
        'volunteers',
        'spreadsheetsIndex',
    )
}

# ======================================================================


def _fix_volunteers(pieces_error, pieces, pd=None, vd=None):
    """Fix the volunteer definitions file.

    Args:
        pieces_error (bool): Whether there was an error fixing the
            piece definitions file.
        pieces (Dict[str, Piece]): The known pieces.
        pd (Optional[str]): A filepath to replace the piece definitions
            file.
        vd (Optional[str]): A filepath to replace the volunteer
            definitions file.

    Returns:
        bool: Whether the fix was successful.
    """
    ERROR_RETURN = False, None

    if pieces_error:
        error('Pieces file could not be read to fix "volunteers"')
        return ERROR_RETURN

    # read the piece definitions (don't fix)
    if pieces is None:
        success, template = read_template()
        if not success:
            return ERROR_RETURN
        success, pieces = read_piece_definitions(template, pd)
        if not success:
            return ERROR_RETURN

    return fix_volunteer_definitions(pieces, vd)

# ======================================================================


@click.command(
    'fix_input',
    help='Fixes input files.'
)
@click.argument('files', type=str, nargs=-1)
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
def fix_input(files, pd, vd, si):
    """Fixes input files.

    Args:
        files (Tuple[str, ...]): The files to fix.
            If none given, all files will be fixed.
        pd (str): A filepath to replace the piece definitions file.
        vd (str): A filepath to replace the volunteer definitions file.
        si (str): A filepath to replace the spreadsheets index file.
    """

    if len(files) == 0:
        files = set(FILES.keys())
    else:
        # filter out unknown files
        filtered = set()
        for file in files:
            if file not in FILES:
                logger.warning('Unknown file key "{}"', file)
                continue
            filtered.add(file)
        files = filtered

    if len(files) == 0:
        logger.info('No files to fix')
        return

    # fix settings
    if 'settings' in files:
        _ = fix_settings()

    # fix pieces
    pieces_error, pieces = False, None
    if 'pieces' in files:
        pieces_error, pieces = fix_piece_definitions(pd)

    # fix volunteers
    if 'volunteers' in files:
        _ = _fix_volunteers(pieces_error, pieces, pd, vd)

    # fix spreadsheets
    if 'spreadsheetsIndex' in files:
        _ = fix_spreadsheets_index(si)
