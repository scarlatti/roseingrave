"""
_piece_summary.py
Export piece JSON data files.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import fail_on_warning, error
from ._read_write import (
    read_template,
    read_piece_definitions,
    read_volunteer_data,
    write_piece_data,
)

# ======================================================================

__all__ = ('piece_summary',)

# ======================================================================


def _copy_fields(email, bar_count, obj, values, replace, location):
    """Copy default fields to an object.
    Displays warnings for extra or missing fields.

    Args:
        email (str): The volunteer email.
        bar_count (int): The number of expected bars.
        obj (Dict): The object to copy to.
        values (Dict): The values to copy.
        replace (bool): Whether to replace the existing value or
            add a field with the email as the key.
        location (str): The location, for error messages.

    Returns:
        Tuple[bool, Dict]: Whether there was a warning,
            and the resulting object.
    """
    warning = False

    unseen_bars = {}
    unseen_keys = {key: True for key in obj.keys()}

    # special case: bars
    if 'bars' not in values:
        warning = True
    else:
        unseen_keys.pop('bars')
        unseen_bars = {str(i + 1): True for i in range(bar_count)}
        obj_bars = obj['bars']
        for bar_num, val in values['bars'].items():
            if bar_num not in obj_bars:
                warning = True
                logger.warning(
                    'Extra bar "{}" for {} (not in range of 1-{})',
                    bar_num, location, bar_count
                )
                continue
            unseen_bars.pop(bar_num)
            if replace:
                obj_bars[bar_num] = val
            elif val != "":
                obj_bars[bar_num][email] = val
    # save all fields except for name, link, and bars
    for key, val in values.items():
        if key in ('name', 'link', 'bars'):
            continue
        if key not in obj:
            warning = True
            logger.warning(
                'Unknown source field "{}" for {} '
                '(not in template definitions file)',
                key, location
            )
            continue
        unseen_keys.pop(key)
        if replace:
            obj[key] = val
        elif val != "":
            obj[key][email] = val

    # warn about missing fields
    if len(unseen_bars) > 0:
        warning = True
        logger.warning(
            'Missing bar numbers {} for {}',
            ','.join(unseen_bars.keys()), location
        )
    if len(unseen_keys) > 0:
        warning = True
        logger.warning(
            'Missing source fields {} for {}',
            ','.join(f'"{k}"' for k in unseen_bars.keys()), location
        )

    return warning

# ======================================================================


def _extract_sources(email,
                     piece,
                     sources,
                     raw_sources,
                     make_default,
                     strict
                     ):
    """Extract sources from a piece.

    Args:
        email (str): The volunteer email, for error messages.
        piece (Piece): The piece this source belongs to.
        sources (Dict[str, Dict]): The existing sources.
        raw_sources (List[Dict]): The sources from the file.
        make_default (Callable): A function to make a default dict.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        bool: Whether the extraction was successful.
    """
    ERROR_RETURN = False

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    piece_location = f'volunteer "{email}", piece "{piece.name}"'

    for i, raw_source in enumerate(raw_sources):
        missing_keys = [
            key for key in ('name', 'link')
            if key not in raw_source
        ]
        if len(missing_keys) > 0:
            return _error(
                'Missing fields {} for {}, source {}',
                ','.join(f'"{key}"' for key in missing_keys),
                piece_location, i
            )

        name = raw_source['name']

        if not piece.has_source(name):
            logger.warning(
                'Unknown source "{}" for {} '
                '(not in piece definitions file)',
                name, piece_location
            )
            if strict:
                fail_on_warning()
                return ERROR_RETURN
            continue

        if name not in sources:
            sources[name] = {
                'name': name,
                'link': raw_source['link'],
                'volunteers': {},
            }

        source = make_default(piece.name)
        warning = _copy_fields(
            email, piece.final_bar_count, source, raw_source, True,
            f'{piece_location}, source "{name}"'
        )
        if strict and warning:
            fail_on_warning()
            return ERROR_RETURN

        sources[name]['volunteers'][email] = source

    return True

# ======================================================================


def _extract_pieces(to_extract,
                    pieces,
                    template,
                    volunteers_data,
                    strict
                    ):
    """Extract pieces from volunteer data files.

    Args:
        to_extract (Tuple[str]): The pieces to extract.
            If empty, all pieces will be extracted.
        pieces (Dict[str, Piece]): A mapping from piece names to piece
            objects.
        template (Dict): The template settings.
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

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    to_extract = set(to_extract)

    def make_default(piece, is_comments=False):
        """Make the default dict for a piece.

        Args:
            piece (str): The piece to make the dict for.
            is_comments (bool): Whether the dict is for comments.
                If True, makes all values empty dicts and excludes the
                "notes" field.
                Default is False.

        Returns:
            Dict[str, Union[str, Dict]]: The dict.
        """

        if is_comments:
            def value():
                return {}
        else:
            def value():
                return ""

        # template names
        values = {
            key: value() for key in template['metaDataFields'].keys()
        }
        # bars
        values['bars'] = {
            str(bar_num + 1): value()
            for bar_num in range(pieces[piece].final_bar_count)
        }
        # notes
        if not is_comments:
            values['notes'] = value()

        return values

    # piece name -> data
    data = {}

    for email, volunteer_data in volunteers_data.items():
        for i, raw_piece in enumerate(volunteer_data):
            missing_keys = [
                key for key in
                ('piece', 'pieceLink', 'sources', 'comments')
                if key not in raw_piece
            ]
            if len(missing_keys) > 0:
                return _error(
                    'Missing fields {} for volunteer "{}", piece {}',
                    ','.join(f'"{key}"' for key in missing_keys),
                    email, i
                )

            title = raw_piece['piece']

            # skip piece
            if len(to_extract) > 0 and title not in to_extract:
                continue

            if title not in pieces:
                logger.warning(
                    'Unknown piece "{}" for volunteer "{}" '
                    '(not in piece definitions file)',
                    title, email
                )
                if strict:
                    fail_on_warning()
                    return ERROR_RETURN
                continue
            piece_obj = pieces[title]

            if title not in data:
                data[title] = {
                    'title': title,
                    'link': raw_piece['pieceLink'],
                    'sources': {},
                    'comments': make_default(title, True),
                }
            piece = data[title]

            # save first link found
            if piece['link'] is None:
                piece['link'] = raw_piece['pieceLink']

            # save all sources
            success = _extract_sources(
                email,
                piece_obj,
                piece['sources'],
                raw_piece['sources'],
                make_default,
                strict
            )
            if not success:
                return ERROR_RETURN

            # save all non-empty comments
            warning = _copy_fields(
                email,
                piece_obj.final_bar_count,
                piece['comments'],
                raw_piece['comments'],
                False,
                f'volunteer "{email}", piece "{title}"'
            )
            if strict and warning:
                fail_on_warning()
                return ERROR_RETURN

    # convert sources from dicts to lists
    for piece in data.values():
        piece['sources'] = list(piece['sources'].values())

    return True, data

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
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def piece_summary(pieces, vdp, td, pd, pdp, strict):
    """Export piece JSON data files.

    Args:
        pieces (Tuple[str, ...]): The pieces to export data for. If none
            given, exports data for all pieces found.
        vdp (str): A filepath to replace the volunteer data path file.
            Must include "{email}" exactly once.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
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

    success, volunteers_data = read_volunteer_data(vdp)
    if not success:
        return

    success, template = read_template(td)
    if not success:
        return

    success, piece_objs = read_piece_definitions(template, pd)
    if not success:
        return

    success, data = _extract_pieces(
        pieces, piece_objs, template, volunteers_data, strict
    )
    if not success:
        return

    if len(data) == 0:
        logger.info('No data found for pieces')
        return

    for piece in pieces:
        if piece not in data:
            logger.warning('No data found for piece "{}"', piece)

    success = write_piece_data(data, pdp)
    if not success:
        return

    logger.info('Done')
