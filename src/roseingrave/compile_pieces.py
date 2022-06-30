"""
compile_pieces.py
Compile all piece JSON data flies into a single file.
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
    read_piece_data,
    write_summary,
)

# ======================================================================

__all__ = ('compile_pieces',)

# ======================================================================


@click.command(
    'compile_pieces',
    help='Compile all piece JSON data flies into a single file.'
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
    '-pdp', type=str,
    help=(
        'A filepath to replace the piece data path file. '
        'Must include "{piece}".'
    )
)
@click.option(
    '-s', 'summary_path', type=str,
    help='A filepath to replace the summary file.'
)
@click.option(
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def compile_pieces(td, pd, pdp, summary_path, strict):
    """Compile all piece JSON data flies into a single file.

    Args:
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
        pdp (str): A filepath to replace the piece data path file.
            Must include "{piece}" exactly once.
        summary_path (str): A filepath to replace the summary file.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.
    """

    # validate args
    if pdp is not None and pdp.count('{piece}') != 1:
        error('`pdp` must include "{piece}" exactly once')
        return

    logger.warning(
        'For most accurate summary, run the `piece_summary` command '
        'first.'
    )

    success, template = read_template(td, strict)
    if not success:
        return

    success, pieces = read_piece_definitions(template, pd, as_data=True)
    if not success:
        return

    success, pieces_data = read_piece_data(pieces, pdp, strict)
    if not success:
        return

    summary = []
    for title, piece in pieces_data.items():
        piece_obj = pieces[title]
        # turn sources into list
        piece['sources'] = list(piece['sources'].values())
        for source in piece['sources']:
            source['summary'] = piece_obj.make_default()
        summary.append(piece)

    success = write_summary(summary, summary_path)
    if not success:
        return

    logger.info('Done')
