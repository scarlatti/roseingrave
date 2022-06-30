"""
_output_files.py
Handles output files.
"""
# Logs all unexpected exceptions
# pylint: disable=broad-except

# ======================================================================

import re
from itertools import zip_longest
from pathlib import Path

from loguru import logger

from ._shared import fail_on_warning, error
from ._read_write import (
    get_path,
    read_json,
    write_json,
    write_json_file,
    read_settings,
)
from ._sheets import (
    gspread_auth,
    open_spreadsheet,
)

# ======================================================================

__all__ = (
    'read_spreadsheets_index', 'write_spreadsheets_index',
    'fix_spreadsheets_index',
    'read_volunteer_data', 'write_volunteer_data',
    'read_piece_data', 'write_piece_data',
    'read_summary', 'write_summary',
)

# ======================================================================


def read_spreadsheets_index(path=None):
    """Read the spreadsheets index file.

    Args:
        path (Optional[str]): A path to the spreadsheets index file to
            use instead.
            Default is None (use the settings file).

    Returns:
        Tuple[bool, Dict[str, str]]: Whether the read was successful,
            and a mapping from volunteer emails to spreadsheet links,
            or an empty dict if the file does not exist.
    """
    ERROR_RETURN = False, None

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Reading spreadsheets index file')

    try:
        contents = read_json('spreadsheetsIndex', path)
    except FileNotFoundError:
        contents = {}
    except ValueError as ex:
        error(ex)
        return ERROR_RETURN
    return True, contents


def write_spreadsheets_index(data, path=None):
    """Write to the spreadsheets index file.
    Updates the file if it exists, or creates it if it doesn't exist.

    Args:
        data (Dict[str, str]): The mapping from volunteer emails to
            spreadsheet links.
        path (Optional[str]): A path to the spreadsheets index file to
            use instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the write was successful.
    """

    success = read_settings()
    if not success:
        return False

    write_json(
        'spreadsheetsIndex', data, path,
        msg='created spreadsheet links'
    )

    return True


def fix_spreadsheets_index(path=None):
    """Fix the spreadsheets index file.

    Args:
        path (Optional[str]): A path to the spreadsheets index file to
            use instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the fix was successful.
    """
    ERROR_RETURN = False

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    success = read_settings()
    if not success:
        return False

    logger.info('Fixing spreadsheets index file')

    try:
        contents = read_json('spreadsheetsIndex', path)
    except (FileNotFoundError, ValueError) as ex:
        return _error(ex)

    # check all links
    fixed = {}
    success, gc = gspread_auth()
    if not success:
        return ERROR_RETURN
    for email, link in contents.items():
        success, _ = open_spreadsheet(gc, link)
        if not success:
            if email == 'MASTER':
                volunteer = 'master spreadsheet'
            else:
                volunteer = f'volunteer "{email}"'
            _error('Removing {}', volunteer)
            continue
        fixed[email] = link

    data = {}
    if 'MASTER' in fixed:
        data['MASTER'] = fixed.pop('MASTER')
    for email, link in sorted(fixed.items()):
        data[email] = link

    write_json(
        'spreadsheetsIndex', data, path,
        msg='fixed spreadsheet links'
    )

    return True


# ======================================================================


def _read_format_files(fmt_path, arg):
    """Read all files matching a formatted path.

    Args:
        fmt_path (Path): The format path.
        arg (str): The arg in the path to match.

    Raises:
        ValueError: If `fmt_path` doesn't include `arg` exactly once.

    Returns:
        Tuple[bool, Dict[str, Union[Dict, List]]]:
            Whether there were any files found, and a mapping from each
            file's arg to the file's parsed contents.
    """
    fmt_path = fmt_path.resolve()

    if str(fmt_path).count(arg) != 1:
        raise ValueError(
            f'path "{fmt_path}" must include "{arg}" exactly once'
        )

    path_parts = fmt_path.parts
    cwd_parts = Path('.').resolve().parts

    # find where they start to differ and where the arg occurs
    differ = None
    arg_index = None
    path_re = None
    for i, (path_part, part) in \
            enumerate(zip_longest(path_parts, cwd_parts)):
        if path_part is not None and arg in path_part:
            arg_index = i
            path_re = re.compile(path_part.replace(arg, '(.+)'))
            if differ is None:
                differ = i
            break

        if differ is None:
            if path_part is None or part is None or path_part != part:
                differ = i

        if differ is not None and arg_index is not None:
            break

    # arg from filepath -> file contents
    data = {}

    num_parts = len(path_parts)

    def check_path(index, curr_path):
        """Check if the current path matches the format path so far,
        and populates data as it goes.
        """

        last_part = index >= num_parts - 1

        if (
            # invalid index
            index >= num_parts or
            # can only be a file when last part
            curr_path.is_file() != last_part
        ):
            return

        current = curr_path.name
        found_arg = None

        if index == arg_index:
            # check match
            match = path_re.match(current)
            if match is None:
                return
            found_arg = match.groups()[0]
        elif current != path_parts[index]:
            return

        # last part
        if last_part:
            if found_arg is not None:
                # add to data
                data[found_arg] = read_json('', str(curr_path))
            return

        # recursively check next
        for path in curr_path.iterdir():
            check_path(index + 1, path)

    # search all files
    for path in Path(*path_parts[:differ]).iterdir():
        check_path(differ, path)

    if len(data) == 0:
        logger.info('No matching files found')
        return False, None

    return True, data

# ======================================================================


def _validate_source(piece,
                     sources,
                     index,
                     raw_source,
                     p_loc,
                     strict,
                     has_volunteers=False,
                     has_summary=False
                     ):
    """Validate a source from an input file.
    Adds the fixed source to `sources`.

    Args:
        piece (PieceData): The piece the source belongs to.
        sources (Dict[str, Dict]): The target sources.
        index (int): The index of this source in the sources array.
        raw_source (Dict): The source JSON dict.
        p_loc (str): The piece location, for error messages.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
        has_volunteers (bool): Whether the raw source has volunteer
            information.
            If False, `raw_source` is expected to have all required
            column fields.
            Default is False.
        has_summary (bool): Whether the raw source has summary
            information.
            If True, `raw_source` is expected to have a "summary" field.
            Default is False.

    Returns:
        bool: Whether there was an error.
    """
    SUCCESS_RETURN = False
    SKIP_RETURN = False
    ERROR_RETURN = True

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    fields = ('name', 'link')
    if has_volunteers:
        fields += ('volunteers',)
    if has_summary:
        fields += ('summary',)
    missing_fields = [
        key for key in fields
        if key not in raw_source
    ]
    if len(missing_fields) > 0:
        return _error(
            'Missing fields {} for {}, source {}',
            ','.join(f'"{key}"' for key in missing_fields),
            p_loc, index
        )

    name = raw_source['name']
    s_link = raw_source['link']

    if not piece.has_source(name):
        logger.warning(
            'Unknown source "{}" for {} '
            '(not in piece definitions file)',
            name, p_loc
        )
        if strict:
            fail_on_warning()
            return ERROR_RETURN
        return SKIP_RETURN

    if name in sources:
        logger.warning('Repeated source "{}" for {}', name, p_loc)
        if strict:
            fail_on_warning()
            return ERROR_RETURN
        return SKIP_RETURN

    s_loc = f'{p_loc}, source "{name}"'

    if s_link != piece.get_source(name).link:
        logger.warning(
            'Incorrect source link "{}" for {}', s_link, s_loc
        )
        if strict:
            fail_on_warning()
            return ERROR_RETURN

    if has_volunteers:
        volunteers = {}
        for email, volunteer in raw_source['volunteers'].items():
            v_loc = f'{s_loc}, volunteer "{email}"'
            warning, fixed = piece.with_defaults(volunteer, v_loc)
            if strict and warning:
                fail_on_warning()
                return ERROR_RETURN
            volunteers[email] = fixed
        adding = {'volunteers': volunteers}
    else:
        warning, source = piece.with_defaults(raw_source, s_loc)
        if strict and warning:
            fail_on_warning()
            return ERROR_RETURN
        adding = source

    if has_summary:
        warning, summary = piece.with_defaults(
            raw_source['summary'], s_loc
        )
        if strict and warning:
            fail_on_warning()
            return ERROR_RETURN
        adding['summary'] = summary

    sources[name] = {
        'name': name,
        'link': s_link,
        **adding,
    }

    return SUCCESS_RETURN


def _validate_piece(pieces,
                    fixed_pieces,
                    v_loc,
                    raw_piece,
                    strict,
                    index=None,
                    from_piece_file=False,
                    file=None,
                    has_summary=False
                    ):
    """Validate a piece from an input file.
    Adds the fixed piece to `fixed_pieces`.

    Args:
        pieces (Dict[str, PieceData]): The known pieces.
        fixed_pieces (Dict[str, Dict]): The target pieces.
        v_loc (Optional[str]): The location of this piece's volunteer,
            for error messages.
            If None, volunteer location is not included in messages.
        raw_piece (Dict): The piece JSON dict.
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
        index (Optional[str[]): The index of this piece.
            Default is None.
        from_piece_file (bool): Whether the input is from a piece file.
            Default is False.
        file (Optional[str]): The name of the file the input came from.
            Default is None.
        has_summary (bool): Whether the sources have summary
            information.
            Default is False.

    Returns:
        bool: Whether there was an error.
    """
    SUCCESS_RETURN = False
    SKIP_RETURN = False
    ERROR_RETURN = True

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    missing_fields = [
        key for key in ('title', 'link', 'sources', 'notes')
        if key not in raw_piece
    ]
    if len(missing_fields) > 0:
        if from_piece_file and file is not None:
            loc = f'piece file "{file}"'
        elif index is not None:
            loc = f'piece {index}'
            if v_loc is not None:
                loc = f'{v_loc}, {loc}'
        else:
            loc = 'piece (location unknown)'
        return _error(
            'Missing fields {} for {}',
            ','.join(f'"{key}"' for key in missing_fields), loc
        )

    title = raw_piece['title']
    p_link = raw_piece['link']

    if from_piece_file and file is not None and file != title:
        msg = f'Piece name "{title}" doesn\'t match file arg "{file}"'
        if strict:
            logger.warning(msg)
            fail_on_warning()
            return ERROR_RETURN
        logger.warning('{}; Using "{}" for piece', msg, title)

    if title not in pieces:
        msg = f'Unknown piece "{title}"'
        if v_loc is not None:
            msg += f' for {v_loc}'
        msg += ' (not in piece definitions file)'
        logger.warning(msg)
        if strict:
            fail_on_warning()
            return ERROR_RETURN
        return SKIP_RETURN
    piece_obj = pieces[title]

    if title in fixed_pieces:
        msg = f'Repeated piece "{title}"'
        if v_loc is not None:
            msg += f' for {v_loc}'
        logger.warning(msg)
        if strict:
            fail_on_warning()
            return ERROR_RETURN
        return SKIP_RETURN

    p_loc = f'piece "{title}"'
    if v_loc is not None:
        p_loc = f'{v_loc}, {p_loc}'

    warning = False
    if piece_obj.link is None:
        if p_link is not None:
            warning = True
            logger.warning(
                'Extra piece link "{}" for {}', p_link, p_loc
            )
    else:
        if p_link is None:
            warning = True
            logger.warning('Missing piece link for {}', p_loc)
        elif p_link != piece_obj.link:
            warning = True
            logger.warning(
                'Incorrect piece link "{}" for {}', p_link, p_loc
            )
    if strict and warning:
        fail_on_warning()
        return ERROR_RETURN

    sources = {}
    for i, raw_source in enumerate(raw_piece['sources']):
        had_error = _validate_source(
            piece_obj, sources, i, raw_source, p_loc, strict,
            has_volunteers=from_piece_file, has_summary=has_summary
        )
        if had_error:
            return ERROR_RETURN
    missing_sources = [
        name for name in piece_obj.all_sources()
        if name not in sources
    ]
    if len(missing_sources) > 0:
        return _error(
            'Missing sources {} for {}',
            ','.join(f'"{name}"' for name in missing_sources), p_loc
        )

    warning, notes = piece_obj.with_defaults(
        raw_piece['notes'], p_loc,
        exclude_comments=True, is_notes=from_piece_file
    )
    if strict and warning:
        fail_on_warning()
        return ERROR_RETURN

    fixed_pieces[title] = {
        'title': title,
        'link': p_link,
        'sources': sources,
        'notes': notes,
    }

    return SUCCESS_RETURN

# ======================================================================


def read_volunteer_data(pieces, fmt_path=None, strict=False):
    """Read volunteer data from files.
    Unknown and repeated pieces and sources will be ignored.

    Args:
        pieces (Dict[str, PieceData]): A mapping from piece names to
            piece data.
        fmt_path (Optional[str]): A format path for volunteer data to
            use instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.

    Returns:
        Tuple[bool, Dict[str, List]]: Whether the read was successful,
            and a mapping from volunteer emails to data.
    """
    ERROR_RETURN = False, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    success = read_settings()
    if not success:
        return ERROR_RETURN

    # validate args
    try:
        path = get_path(
            'volunteerDataPath', fmt_path,
            must_exist=False
        )
    except Exception as ex:
        return _error(ex)
    if str(path).count('{email}') != 1:
        return _error(
            'Path to volunteer data files must include "{email}" '
            'exactly once'
        )

    logger.info('Reading volunteer data from files: {}', path)

    success, raw_data = _read_format_files(path, '{email}')
    if not success:
        return ERROR_RETURN

    # validate data
    volunteers = {}
    for email, volunteer_pieces in raw_data.items():
        v_loc = f'volunteer "{email}"'
        fixed_pieces = {}
        for i, raw_piece in enumerate(volunteer_pieces):
            had_error = _validate_piece(
                pieces, fixed_pieces, v_loc, raw_piece, strict, i
            )
            if had_error:
                return ERROR_RETURN
        volunteers[email] = fixed_pieces

    return True, volunteers


def write_volunteer_data(data, fmt_path=None):
    """Write volunteer data to files.
    Replaces files if they already exist.

    Args:
        data (Dict[str, List]): A mapping from volunteer emails to data.
        fmt_path (Optional[str]): A format path for volunteer data to
            use instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the write was successful.
    """

    def _error(msg):
        return error(msg, False)

    success = read_settings()
    if not success:
        return False

    # validate args
    try:
        path = str(get_path(
            'volunteerDataPath', fmt_path,
            must_exist=False
        ))
    except Exception as ex:
        return _error(ex)
    if path.count('{email}') != 1:
        return _error(
            'Path to volunteer data files must include "{email}" '
            'exactly once'
        )

    logger.info('Writing volunteer data to files: {}', path)

    for email, volunteer_data in data.items():
        write_json_file(path.format(email=email), volunteer_data)

    return True

# ======================================================================


def read_piece_data(pieces, fmt_path=None, strict=False):
    """Read piece data from files.

    Args:
        pieces (Dict[str, PieceData]): A mapping from piece names to
            piece data.
        fmt_path (Optional[str]): A format path for piece data to use
            instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.

    Returns:
        Tuple[bool, Dict[str, Dict]]: Whether the read was successful,
            and a mapping from piece names to data.
    """
    ERROR_RETURN = False, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    success = read_settings()
    if not success:
        return ERROR_RETURN

    # validate args
    try:
        path = get_path('pieceDataPath', fmt_path, must_exist=False)
    except Exception as ex:
        return _error(ex)
    if str(path).count('{piece}') != 1:
        return _error(
            'Path to piece data files must include "{piece}" exactly '
            'once'
        )

    logger.info('Reading piece data from files: {}', path)

    success, raw_data = _read_format_files(path, '{piece}')
    if not success:
        return ERROR_RETURN

    # validate data
    # FUTURE: can validate that certain volunteer emails show up?
    #   i.e., all sources must have the same volunteers, and the
    #   emails in "notes" must be a subset
    pieces_data = {}
    for file, raw_piece in raw_data.items():
        had_error = _validate_piece(
            pieces, pieces_data, None, raw_piece, strict,
            from_piece_file=True, file=file
        )
        if had_error:
            return ERROR_RETURN

    return True, pieces_data


def write_piece_data(data, fmt_path=None):
    """Write piece data to files.
    Replaces files if they already exist.

    Args:
        data (Dict[str, Dict]): A mapping from piece names to data.
        fmt_path (Optional[str]): A format path for piece data to use
            instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the write was successful.
    """

    def _error(msg):
        return error(msg, False)

    success = read_settings()
    if not success:
        return False

    # validate args
    try:
        path = str(get_path(
            'pieceDataPath',
            fmt_path, must_exist=False
        ))
    except Exception as ex:
        return _error(ex)
    if path.count('{piece}') != 1:
        return _error(
            'Path to piece data files must include "{piece}" exactly '
            'once'
        )

    logger.info('Writing piece data to files: {}', path)

    for piece, piece_data in data.items():
        write_json_file(path.format(piece=piece), piece_data)

    return True

# ======================================================================


def read_summary(pieces, path=None, strict=False):
    """Read from the summary file.
    Validates the data in the file.

    Args:
        pieces (Dict[str, PieceData]): A mapping from piece names to
            piece data.
        path (Optional[str]): A path to the summary file to use instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.

    Returns:
        Tuple[bool, Dict[str, Dict]]: Whether the read was successful,
            and a mapping from piece names to piece summary data.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Reading summary file')

    key = 'summary'

    try:
        values = read_json(key, path)
    except FileNotFoundError as ex:
        return _error(ex)

    # validate data
    summary = {}
    for i, raw_piece in enumerate(values):
        had_error = _validate_piece(
            pieces, summary, None, raw_piece, strict,
            index=i, from_piece_file=True, has_summary=True
        )
        if had_error:
            return ERROR_RETURN

    return True, summary


def write_summary(summary, path=None):
    """Write to the summary file.

    Args:
        summary (List[Dict]): The summary.
        path (Optional[str]): A path to the summary file to use instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the write was successful.
    """

    success = read_settings()
    if not success:
        return False

    write_json('summary', summary, path, msg='summary')
    return True
