"""
_compile_pieces.py
Compile all piece JSON data flies into a single file.
"""

# ======================================================================

import click
from loguru import logger

from ._shared import fail_on_warning, error
from ._read_write import (
    read_template,
    read_piece_definitions,
    read_piece_data,
    write_summary,
)

# ======================================================================

__all__ = ('compile_pieces',)

# ======================================================================


def _make_summary(template, pieces, data, strict):
    """Make the piece summary.

    Args:
        template (Dict): The template settings.
        pieces (Dict[str, Piece]): A mapping from piece names to piece
            objects.
        data (Dict[str, Dict]): A mapping from piece names to data.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        Tuple[bool, List[Dict]]: Whether the summary was successfully
            made, and the piece summary.
    """
    ERROR_RETURN = False, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    def make_default(bar_count, is_comments=False):
        """Make the default dict with the given bar count."""

        if is_comments:
            def value():
                return {}
        else:
            def value():
                return ""

        # template names
        values = {
            key: value()
            for key in template['metaDataFields'].keys()
        }
        # bars
        values['bars'] = {
            str(i + 1): value()
            for i in range(bar_count)
        }
        # notes
        if not is_comments:
            values['notes'] = value()

        return values

    def fix_obj(bar_count, obj, location, is_comments=False):
        """Check that an object has all the required fields.
        Returns whether the check was successful,
        and a copy of the object with all the required fields filtered.
        """

        fixed = make_default(bar_count, is_comments)

        extra_bars = []
        missing_bars = {}
        unknown_fields = []
        missing_fields = {key: True for key in fixed.keys()}

        # special case: bars
        if 'bars' in obj:
            missing_fields.pop('bars')
            missing_bars = {str(i + 1): True for i in range(bar_count)}
            bars = fixed['bars']
            for bar_num, val in obj['bars'].items():
                if bar_num not in bars:
                    extra_bars.append(bar_num)
                    continue
                missing_bars.pop(bar_num)
                bars[bar_num] = val
        # save all fields except for name, link, and bars
        for key, val in obj.items():
            if key in ('name', 'link', 'bars'):
                continue
            if key not in fixed:
                unknown_fields.append(key)
                continue
            missing_fields.pop(key)
            fixed[key] = val

        # warn about extra fields
        warning = False
        if len(extra_bars) > 0:
            warning = True
            logger.warning(
                'Extra bars {} for {} (not in range of 1-{})',
                ','.join(extra_bars), location, bar_count
            )
        if len(unknown_fields) > 0:
            warning = True
            logger.warning(
                'Unknown fields {} for {} '
                '(not in template definitions file)',
                ','.join(f'"{key}"' for key in unknown_fields), location
            )

        # missing fields
        invalid = False
        if len(missing_fields) > 0:
            invalid = True
            logger.error(
                'Missing fields {} for {}',
                ','.join(f'"{key}"' for key in missing_fields.keys()),
                location
            )
        if len(missing_bars) > 0:
            invalid = True
            logger.error(
                'Missing bar numbers {} for {}',
                ','.join(missing_bars.keys()), location
            )
        if invalid:
            return False, None

        if strict and warning:
            fail_on_warning()
            return False, None

        return True, fixed

    logger.info('Making summary of pieces')

    summary = []
    for file, piece_data in data.items():
        missing_fields = [
            key for key in ('title', 'link', 'sources', 'comments')
            if key not in piece_data
        ]
        if len(missing_fields) > 0:
            return _error(
                'Missing fields {} for piece "{}"',
                ','.join(f'"{key}"' for key in missing_fields), file
            )

        title = piece_data['title']
        bar_count = pieces[title].final_bar_count

        piece_location = f'piece "{title}"'

        sources = []
        for i, source in enumerate(piece_data['sources']):
            missing_fields = [
                key for key in ('name', 'link', 'volunteers')
                if key not in source
            ]
            if len(missing_fields) > 0:
                return _error(
                    'Missing fields {} for {}, source {}',
                    ','.join(f'"{key}"' for key in missing_fields),
                    piece_location, i
                )

            name = source['name']

            source_location = f'{piece_location}, source "{name}"'

            volunteers = {}
            for email, volunteer in source['volunteers'].items():
                success, fixed = fix_obj(
                    bar_count, volunteer,
                    f'{source_location}, volunteer "{email}"'
                )
                if not success:
                    return ERROR_RETURN
                volunteers[email] = fixed

            # add "summary"
            volunteers['summary'] = make_default(bar_count)

            sources.append({
                'name': name,
                'link': source['link'],
                'volunteers': volunteers,
            })

        success, comments = fix_obj(
            bar_count, piece_data['comments'], piece_location, True
        )
        if not success:
            return ERROR_RETURN

        summary.append({
            'title': title,
            'link': piece_data['link'],
            'sources': sources,
            'comments': comments,
        })

    return True, summary


# ======================================================================


@click.command(
    'compile_pieces',
    help='Compile all piece JSON data flies into a single file.'
)
@click.option(
    '-pdp', type=str,
    help=(
        'A filepath to replace the piece data path file. '
        'Must include "{piece}".'
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
    '-s', 'summary_path', type=str,
    help='A filepath to replace the summary file.'
)
@click.option(
    '--strict', is_flag=True, default=False, flag_value=True,
    help='Fail on warnings instead of only displaying them.'
)
def compile_pieces(pdp, td, pd, summary_path, strict):
    """Compile all piece JSON data flies into a single file.

    Args:
        pdp (str): A filepath to replace the piece data path file.
            Must include "{piece}" exactly once.
        td (str): A filepath to replace the template definitions file.
        pd (str): A filepath to replace the piece definitions file.
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

    success, pieces_data = read_piece_data(pdp)
    if not success:
        return

    success, template = read_template(td, strict)
    if not success:
        return

    success, pieces = read_piece_definitions(template, pd)
    if not success:
        return

    success, summary = _make_summary(
        template, pieces, pieces_data, strict
    )
    if not success:
        return

    success = write_summary(summary, summary_path)
    if not success:
        return

    logger.info('Done')
