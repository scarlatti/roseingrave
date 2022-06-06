"""
_read_write.py
Read and write operations on files.
"""

# ======================================================================

import json
import re
from itertools import zip_longest
from pathlib import Path

from loguru import logger

from ._shared import fail_on_warning, error
from ._piece import Piece
from ._piece_data import PieceData
from ._volunteer import Volunteer

# ======================================================================

__all__ = (
    'read_template',
    'read_piece_definitions',
    'read_volunteer_definitions',
    'read_spreadsheets_index', 'write_spreadsheets_index',
    'read_volunteer_data', 'write_volunteer_data',
    'read_piece_data', 'write_piece_data',
    'read_summary', 'write_summary',
)

# ======================================================================

SETTINGS_FILE = 'roseingrave.json'

# every time the script is run, this gets populated for that run
# becomes flattened version of the file
SETTINGS = {}

# required fields and default values for input files
FILES = {
    'settings': {
        # the default settings
        'credentials': 'credentials.json',
        'definitionFiles': {
            'template': ['input', 'template_definitions.json'],
            'pieces': ['input', 'piece_definitions.json'],
            'volunteers': ['input', 'volunteer_definitions.json'],
        },
        'outputs': {
            'spreadsheetsIndex': ['output', 'spreadsheets.json'],
            'volunteerDataPath': [
                'output', 'data', 'by-volunteer', '{email}.json'
            ],
            'pieceDataPath': [
                'output', 'data', 'by-piece', '{piece}.json'
            ],
            'summary': ['output', 'summary.json'],
        },
    },
    'template': {
        # the default template
        'masterSpreadsheet': {
            'title': 'Master Spreadsheet',
            'publicAccess': None,
            'shareWith': [],
        },
        'volunteerSpreadsheet': {
            'title': '{email}',
            'publicAccess': None,
            'shareWithVolunteer': True,
            'shareWith': [],
            'resize': True,
        },
        'metaDataFields': {
            'title': 'Title',
            'tempo': 'Tempo',
            'clefs': 'Clefs (if other than G and F)',
            'keySig': 'Key sig.',
            'timeSig': 'Time sig.',
            'barCount': 'Number of bars',
            'compassHigh': 'Highest pitch note',
            'compassLow': 'Lowest pitch note',
            'hand': 'Hand signs',
            'endSigns': 'Endings signs',
            'repeatSigns': 'Repeat signs',
            'articulation': 'Articulation signs',
            'dynamic': 'Dynamic signs',
            'otherIndications': 'Other indications',
        },
        'commentFields': {
            'notes': 'Notes',
            'comments': 'Comments',
            'summary': 'SUMMARY',
        },
        'values': {
            'defaultBarCount': 100,
            'commentsRowHeight': 75,
        },
    },
}
# the options for the "publicAccess" field
PUBLIC_ACCESS_OPTIONS = (None, 'view', 'edit')

# ======================================================================


def _get_path(key, path=None, must_exist=True, create_dirs=False):
    """Get the path for a file key.

    Args:
        key (str): The key representing the file.
        path (Optional[str]): A path to the file to use instead.
            Default is None (use the settings file).
        must_exist (bool): Whether the file must exist.
            Default is True.
        create_dirs (bool): Whether to create missing parent
            directories.
            Default is False.

    Raises:
        ValueError: If `path` is None and the key is invalid.
        ValueError: If the file does not have extension ".json".
        FileNotFoundError: If `must_exist` is True
            and the file is not found.

    Returns:
        Path: The path to the file.
    """

    if path is None:
        if key not in SETTINGS:
            raise ValueError(f'invalid file key "{key}"')
        path = SETTINGS[key]
    else:
        path = [path]
    if not path[-1].endswith('.json'):
        raise ValueError('path must have extension ".json"')

    filepath = Path(*path)
    if must_exist and not filepath.exists():
        raise FileNotFoundError(f'file "{filepath}" not found')
    if create_dirs:
        filepath.parent.mkdir(parents=True, exist_ok=True)
    return filepath

# ======================================================================


def _read_json(key, path=None):
    """Read data from a JSON file.

    Args:
        key (str): The key representing the file.
        path (Optional[str]): A path to the file to use instead.
            Default is None (use the settings file).

    Raises:
        ValueError: If `path` is None and the key is invalid.
        FileNotFoundError: If the file is not found.

    Returns:
        Union[Dict, List]: The contents of the JSON file.
    """
    filepath = _get_path(key, path)
    contents = filepath.read_text(encoding='utf-8')
    return json.loads(contents)


def _write(filepath, data, msg):
    if msg is not None:
        logger.info('Writing {} to "{}"', msg, filepath)
    filepath.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _write_json(key, data, path=None, msg=None):
    """Write data to a JSON file.
    Creates the file and any parent directories.
    Overwrites file if already exists.

    Args:
        key (str): The key representing the file.
        data (Dict): The data to write.
        path (Optional[str]): A path to the file to use instead.
            Default is None (use the settings file).
        msg (Optional[str]): A message to log.
            If None, nothing is displayed.
            Default is None.

    Raises:
        ValueError: If `path` is None and the key is invalid.
    """
    filepath = _get_path(key, path, must_exist=False, create_dirs=True)
    _write(filepath, data, msg)


def _write_json_file(path, data, msg=None):
    """Write data to a JSON file.
    Creates the file and any parent directories.
    Overwrites file if already exists.

    Args:
        path (str): A path to the file.
        data (Dict): The data to write.
        msg (Optional[str]): A message to log.
            If None, nothing is displayed.
            Default is None.
    """
    filepath = Path(path)
    # make parent directories
    filepath.parent.mkdir(parents=True, exist_ok=True)
    _write(filepath, data, msg)

# ======================================================================


def _read_settings():
    """Read the settings file and update the `SETTINGS` global variable.

    Returns:
        bool: Whether the read was successful.
    """
    ERROR_RETURN = False

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    if len(SETTINGS) > 0:
        return True

    logger.info('Reading settings file')

    try:
        raw_values = _read_json('', SETTINGS_FILE)
    except FileNotFoundError:
        # no settings file, so just use all defaults
        raw_values = {}

    # no required fields

    # add defaults if missing
    defaults = FILES['settings']

    # credentials
    path = raw_values.get('credentials', defaults['credentials'])
    if isinstance(path, str):  # turn into list if a str
        path = [path]
    SETTINGS['credentials'] = path
    SETTINGS['authorized_user'] = path[:-1] + ['authorized_user.json']

    for level, level_defaults in defaults.items():
        # already took care of credentials
        if level in ('credentials',):
            continue
        values = raw_values.get(level, {})
        for k, default in level_defaults.items():
            path = values.get(k, default)
            if isinstance(path, str):  # turn into list if a str
                path = [path]
            SETTINGS[k] = path

    # validate values
    for key, search in (
        ('volunteerDataPath', '{email}'),
        ('pieceDataPath', '{piece}'),
    ):
        count = sum(
            path_piece.count(search)
            for path_piece in SETTINGS[key]
        )
        if count != 1:
            return _error(
                '"{}" must have "{}" exactly once', key, search
            )

    return True

# ======================================================================


def read_template(path=None, strict=False):
    """Read the template definitions file.

    Args:
        path (Optional[str]): A path to the template definitions file to
            use instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.

    Returns:
        Tuple[bool, Dict]: Whether the read was successful,
            and the template settings.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Reading template definitions file')

    key = 'template'

    try:
        raw_values = _read_json(key, path)
    except FileNotFoundError as ex:
        return _error(ex)
    values = {}
    invalid = False
    warning = False

    # no required fields

    # add defaults if missing
    for level, level_defaults in FILES[key].items():
        level_values = raw_values.get(level, {})
        values[level] = {}
        for k, default in level_defaults.items():
            values[level][k] = level_values.get(k, default)
    # validation
    values['validation'] = {}
    for k, validation in raw_values.get('validation', {}).items():
        if k not in values['metaDataFields']:
            warning = True
            logger.warning('validation: unknown key "{}"', k)
            continue
        if 'type' not in validation:
            warning = True
            logger.warning('"{}" validation: no type', k)
            continue
        v_type = validation['type']
        if v_type == 'checkbox':
            values['validation'][k] = {'type': 'checkbox'}
        elif v_type == 'dropdown':
            if len(validation.get('values', [])) == 0:
                warning = True
                logger.warning(
                    '"{}" validation: no values for dropdown', k
                )
                continue
            values['validation'][k] = {
                'type': 'dropdown',
                'values': validation['values'],
            }
        else:
            warning = True
            logger.warning(
                '"{}" validation: unknown type "{}"', k, v_type
            )

    # validate values
    # public access options
    for ss in ('masterSpreadsheet', 'volunteerSpreadsheet'):
        value = values[ss]['publicAccess']
        if value not in PUBLIC_ACCESS_OPTIONS:
            warning = True
            logger.warning(
                '"{}"."publicAccess": invalid value "{}" '
                '(must be null, "view", or "edit")',
                ss, value
            )
            # reset to default
            values[ss]['publicAccess'] = FILES[key][ss]['publicAccess']
    # volunteer spreadsheet title must have "{email}" at most once
    if values['volunteerSpreadsheet']['title'].count('{email}') > 1:
        invalid = True
        _error(
            '"volunteerSpreadsheet"."title": '
            'can only contain "{email}" at most once'
        )
    # must be a boolean
    for k in ('shareWithVolunteer', 'resize'):
        val = values['volunteerSpreadsheet'][k]
        if val not in (True, False):
            warning = True
            logger.warning(
                '"volunteerSpreadsheet"."{}": invalid value "{}" '
                '(must be true or false)',
                k, val
            )
            # reset to default
            values['volunteerSpreadsheet'][k] = \
                FILES[key]['volunteerSpreadsheet'][k]
    # default bar count must be positive
    if values['values']['defaultBarCount'] <= 0:
        invalid = True
        _error('"defaultBarCount" must be positive')
    # comments row height must be at least 21
    if values['values']['commentsRowHeight'] < 21:
        invalid = True
        _error('"commentsRowHeight" must be at least 21')

    if invalid:
        return ERROR_RETURN
    if strict and warning:
        fail_on_warning()
        return ERROR_RETURN

    return True, values

# ======================================================================


def read_piece_definitions(template,
                           path=None,
                           as_data=False,
                           as_both=False
                           ):
    """Read the piece definitions file.
    Repeated pieces and sources will be combined.

    Args:
        template (Dict): The template settings.
        path (Optional[str]): A path to the piece definitions file to
            use instead.
            Default is None (use the settings file).
        as_data (bool): Whether to return the piece objects as data.
            Default is False.
        as_both (bool): Whether to return the piece objects as both
            regular objects and as data.
            If True, returns a tuple of piece objects and piece data in
            place of the mapping.
            Default is False.

    Returns:
        Tuple[bool, Dict[str, Union[Piece, PieceData]]]:
            Whether the read was successful,
            and a mapping from piece names to piece objects.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    logger.info('Reading piece definitions file')
    try:
        raw_pieces = _read_json('pieces', path)
    except FileNotFoundError as ex:
        return _error(ex)
    if len(raw_pieces) == 0:
        return _error('no pieces found')

    pieces = {}
    for i, args in enumerate(raw_pieces):
        try:
            piece = Piece(args, template)
        except ValueError as ex:
            return _error(f'piece {i}: {ex}')

        name = piece.name
        if name in pieces:
            # combine sources with previous piece
            logger.debug('Combining piece "{}"', name)
            pieces[name].combine(piece)
        else:
            pieces[name] = piece

    # check that all pieces have sources
    invalid = False
    for piece in pieces.values():
        if len(piece.sources) == 0:
            invalid = True
            _error(f'piece "{piece.name}": no sources found')
    if invalid:
        return ERROR_RETURN

    if as_both or as_data:
        pieces_data = {
            title: PieceData(piece)
            for title, piece in pieces.items()
        }
        if as_both:
            return True, (pieces, pieces_data)
        pieces = pieces_data

    return True, pieces

# ======================================================================


def read_volunteer_definitions(pieces, path=None, strict=False):
    """Read the volunteer definitions file.
    Repeated volunteers will be combined.
    Unknown pieces will be ignored.

    Args:
        template (Dict): The template settings.
        path (Optional[str]): A path to the piece definitions file to
            use instead.
            Default is None (use the settings file).

    Returns:
        Tuple[bool, Dict[str, Volunteer]]:
            Whether the read was successful,
            and a mapping from volunteer emails to volunteer objects.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    logger.info('Reading volunteer definitions file')
    try:
        raw_volunteers = _read_json('volunteers', path)
    except FileNotFoundError as ex:
        return _error(ex)
    if len(raw_volunteers) == 0:
        return _error('no volunteers found')

    volunteers = {}
    unknown_pieces = False
    for i, args in enumerate(raw_volunteers):
        try:
            volunteer = Volunteer(args, pieces)
        except ValueError as ex:
            return _error(f'volunteer {i}: {ex}')

        email = volunteer.email
        if email in volunteers:
            # combine pieces with previous volunteer
            logger.debug('Combining volunteer "{}"', email)
            volunteers[email].combine(volunteer)
        else:
            volunteers[email] = volunteer

        for piece in volunteer.unknown_pieces:
            unknown_pieces = True
            logger.warning('volunteer {}: unknown piece "{}"', i, piece)

    # check that all volunteers have pieces
    invalid = False
    for volunteer in volunteers.values():
        if len(volunteer.pieces) == 0:
            invalid = True
            _error(f'volunteer "{volunteer.email}": no pieces found')

    if invalid:
        return ERROR_RETURN
    if strict and unknown_pieces:
        fail_on_warning()
        return ERROR_RETURN

    return True, volunteers

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

    success = _read_settings()
    if not success:
        return False, None

    logger.info('Reading spreadsheets index file')
    try:
        contents = _read_json('spreadsheetsIndex', path)
    except FileNotFoundError:
        contents = {}
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

    success = _read_settings()
    if not success:
        return False

    _write_json(
        'spreadsheetsIndex', data, path,
        msg='created spreadsheet links'
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
                data[found_arg] = _read_json('', str(curr_path))
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

    if piece_obj.link is None:
        if p_link is not None:
            logger.warning(
                'Extra piece link "{}" for {}', p_link, p_loc
            )
            if strict:
                fail_on_warning()
                return ERROR_RETURN
    else:
        if p_link is None:
            logger.warning('Missing piece link for {}', p_loc)
            if strict:
                fail_on_warning()
                return ERROR_RETURN
        elif p_link != piece_obj.link:
            logger.warning(
                'Incorrect piece link "{}" for {}', p_link, p_loc
            )
            if strict:
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

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    # validate args
    try:
        path = _get_path(
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

    success = _read_settings()
    if not success:
        return False

    # validate args
    try:
        path = str(_get_path(
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
        _write_json_file(path.format(email=email), volunteer_data)

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

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    # validate args
    try:
        path = _get_path('pieceDataPath', fmt_path, must_exist=False)
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

    success = _read_settings()
    if not success:
        return False

    # validate args
    try:
        path = str(_get_path(
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
        _write_json_file(path.format(piece=piece), piece_data)

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

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Reading summary file')

    key = 'summary'

    try:
        values = _read_json(key, path)
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

    success = _read_settings()
    if not success:
        return False

    _write_json('summary', summary, path, msg='summary')
    return True
