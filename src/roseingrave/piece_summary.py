"""
piece_summary.py
Export piece JSON data files.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import error
from ._input_files import (
    read_template,
    read_piece_definitions,
)
from ._output_files import (
    read_volunteer_data,
    write_piece_data,
)

# ======================================================================

__all__ = ('piece_summary',)

# ======================================================================


def _extract_pieces(pieces, volunteers_data, strict):
    """Extract pieces from volunteer data files.

    Args:
        pieces (Dict[str, PieceData]): A mapping from piece names to
            piece objects.
            Only includes the pieces needed.
        volunteers_data (Dict[str, List]): A mapping from volunteer
            emails to data.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        Tuple[bool, Dict[str, Dict]]:
            Whether the extraction was successful, and
            a mapping from piece names to data.
    """
    ERROR_RETURN = False, None

    logger.info('Extracting pieces from volunteer data files')

    seen = {title: False for title in pieces.keys()}

    for email, volunteer_data in volunteers_data.items():
        for title, piece in volunteer_data.items():
            # not being extracted, so ignore
            if title not in pieces:
                continue
            seen[title] = True
            success = pieces[title].add_volunteer(email, piece, strict)
            if not success:
                return ERROR_RETURN

    # convert PieceData to dicts
    # only include the ones actually seen
    data = {
        title: piece.to_json()
        for title, piece in pieces.items()
        if seen[title]
    }

    if len(data) == 0:
        logger.info('No data found for pieces')
        return ERROR_RETURN

    return True, data

# ======================================================================


@click.command(
    'piece_summary',
    help='Export piece JSON data files.',
)
@click.argument('pieces', type=str, nargs=-1)
@click.option(
    '-td', type=str,
    help='A filepath to replace the template definitions file.'
)
@click.option(
    '-pd', type=str,
    help='A filepath to replace the piece definitions file.'
)
@click.option(
    '-vdp', type=str,
    help=(
        'A filepath to replace the volunteer data path file. '
        'Must include "{email}".'
    )
)
@click.option(
    '-pdp', type=str,
    help=(
        'A filepath to replace the piece data path file. '
        'Must include "{piece}".'
    )
)
@click.option(
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def piece_summary(pieces, td, pd, vdp, pdp, strict):
    """Export piece JSON data files.

    Args:
        pieces (Tuple[str, ...]): The pieces to export data for. If none
            given, exports data for all pieces found.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        vdp (str): A filepath to replace the volunteer data path file.
            Must include "{email}" exactly once.
        pdp (str): A filepath to replace the piece data path file.
            Must include "{piece}" exactly once.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    # validate args
    if vdp is not None and vdp.count('{email}') != 1:
        error('`vdp` must include "{email}" exactly once')
        return
    if pdp is not None and pdp.count('{piece}') != 1:
        error('`pdp` must include "{piece}" exactly once')
        return

    logger.warning(
        'For most accurate summary, run the `volunteer_summary` '
        'command first.'
    )

    success, template = read_template(td, strict)
    if not success:
        return

    success, piece_data = read_piece_definitions(
        template, pd, as_data=True
    )
    if not success:
        return

    success, volunteers_data = read_volunteer_data(
        piece_data, vdp, strict
    )
    if not success:
        return

    # filter the pieces to extract
    if len(pieces) > 0:
        filtered = {}
        for piece in pieces:
            if piece not in piece_data:
                logger.warning(
                    'Piece "{}" not found in piece definitions file',
                    piece
                )
                continue
            filtered[piece] = piece_data[piece]
        piece_data = filtered

    if len(piece_data) == 0:
        logger.info('No pieces to summarize data for')
        return

    success, data = _extract_pieces(piece_data, volunteers_data, strict)
    if not success:
        return

    for piece in pieces:
        if piece not in data:
            logger.warning('No data found for piece "{}"', piece)

    success = write_piece_data(data, pdp)
    if not success:
        return

    logger.info('Done')
