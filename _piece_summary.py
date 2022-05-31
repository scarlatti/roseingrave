"""
_piece_summary.py
Export piece JSON data files.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import error
from ._read_write import (
    read_volunteer_data,
    write_piece_data,
)

# ======================================================================

__all__ = ('piece_summary',)

# ======================================================================


def extract_pieces(pieces, volunteers_data):
    """Extract pieces from volunteer data files.

    Args:
        pieces (Tuple[str]): The pieces to extract.
            If empty, all pieces will be extracted.
        volunteers_data (Dict[str, Json]): A mapping from volunteer
            emails to data.
    """
    pieces = set(pieces)

    # piece name -> data
    data = {}
    # piece name -> source name -> index
    piece_sources = {}

    for email, volunteer_data in volunteers_data.items():
        for piece in volunteer_data:
            # skip piece
            title = piece['piece']
            if len(pieces) > 0 and title not in pieces:
                continue

            if title not in data:
                data[title] = {
                    'title': title,
                    'link': piece['pieceLink'],
                    'sources': [],
                    'comments': {
                        # copy over all the keys
                        key: {} for key in piece['comments'].keys()
                    },
                }
                if 'bars' in piece['comments']:
                    # copy over all the bars
                    data[title]['comments']['bars'] = {
                        key: {}
                        for key in piece['comments']['bars'].keys()
                    }
                piece_sources[title] = {}

            piece_data = data[title]
            source_names = piece_sources[title]

            # save first link found
            if piece_data['link'] is None:
                piece_data['link'] = piece['pieceLink']

            # save all sources
            sources = piece_data['sources']
            for source in piece['sources']:
                name = source['name']
                if name not in source_names:
                    source_names[name] = len(sources)
                    sources.append({
                        'name': name,
                        'link': source['link'],
                        'volunteers': {},
                    })
                # save all fields except for name and link
                sources[source_names[name]]['volunteers'][email] = {
                    key: val for key, val in source.items()
                    if key not in ('name', 'link')
                }

            # save all non-empty comments
            comments = piece_data['comments']
            # special case
            if 'bars' in piece['comments']:
                include_all = False
                if 'bars' not in comments:
                    comments['bars'] = {}
                    include_all = True
                bar_comments = comments['bars']
                for bar_num, comment in \
                        piece['comments'].pop('bars').items():
                    if not include_all and comment == "":
                        continue
                    if bar_num not in bar_comments:
                        # to be safe, create extra field
                        bar_comments[bar_num] = {}
                    bar_comments[bar_num][email] = comment
            # the rest of the comments
            for key, comment in piece['comments'].items():
                if comment == "":
                    continue
                if key not in comments:
                    # to be safe, create extra field
                    comments[key] = {}
                comments[key][email] = comment

    return data

# ======================================================================


@click.command(
    'piece_summary',
    help='Export piece JSON data files.',
)
@click.argument('pieces', type=str, nargs=-1)
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
def piece_summary(pieces, vdp, pdp):
    """Export piece JSON data files.

    Args:
        pieces (Tuple[str, ...]): The pieces to export data for. If none
            given, exports data for all pieces found.
        vdp (str): A filepath to replace the volunteer data path file.
            Must include "{email}" exactly once.
        pdp (str): A filepath to replace the piece data path file.
            Must include "{piece}" exactly once.
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

    success, volunteers_data = read_volunteer_data(vdp)
    if not success:
        return

    data = extract_pieces(pieces, volunteers_data)

    if len(data) == 0:
        logger.info('No data found for pieces')
        return

    for piece in pieces:
        if piece not in data:
            logger.warning(f'No data found for piece "{piece}"')

    success = write_piece_data(data, pdp)
    if not success:
        return

    logger.info('Done')
