"""
_read_write.py
Read and write operations on files.
"""

# ======================================================================

import json
import re
from pathlib import Path

from loguru import logger

from ._shared import fail_on_warning, error
from ._piece import Piece
from ._volunteer import Volunteer

# ======================================================================

__all__ = (
    'read_template',
    'read_definitions',
    'read_spreadsheets_index', 'write_spreadsheets_index',
    'read_volunteer_data', 'write_volunteer_data',
    'write_piece_data',
)

# ======================================================================

SETTINGS_FILE = 'roseingrave.json'

# every time the script is run, this gets populated for that run
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
            'pieceSummary': ['output', 'summary.json'],
            'volunteerDataPath': [
                'output', 'data', 'by-volunteer', '{email}.json'
            ],
            'pieceDataPath': [
                'output', 'data', 'by-piece', '{piece}.json'
            ],
        },
    },
    'template': {
        # the default template
        'metaDataFields': {
            'title': 'Title',
            'tempo': 'Tempo',
            'key': 'Key',
            'keySig': 'Key sig.',
            'timeSig': 'Time sig.',
            'barCount': 'Bars',
            'compass': 'Compass',
            'clefs': 'Clefs (if other than G and F)',
            'endOrRepeat': 'Endings and Repeat signs',
            'articulation': 'Articulation signs',
            'dynamic': 'Dynamic signs',
            'hand': 'Hand signs',
            'otherIndications': 'Other indications',
        },
        'commentFields': {
            'comments': 'Comments',
            'notes': 'Notes',
        },
        'values': {
            'defaultBarCount': 100,
            'notesRowHeight': 75,
        },
    },
}

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
        logger.info(f'Writing {msg} to "{filepath}"')
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

    def _error(msg):
        return error(msg, ERROR_RETURN)

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

    path = raw_values.get('credentials', defaults['credentials'])
    if isinstance(path, str):  # turn into list if a str
        path = [path]
    SETTINGS['credentials'] = path
    SETTINGS['authorized_user'] = path[:-1] + ['authorized_user.json']

    for level in ('definitionFiles', 'outputs'):
        values = raw_values.get(level, {})
        for k, default in defaults[level].items():
            path = values.get(k, default)
            if isinstance(path, str):  # turn into list if a str
                path = [path]
            SETTINGS[k] = path

    for key, search in (
        ('volunteerDataPath', '{email}'),
        ('pieceDataPath', '{piece}'),
    ):
        if not any(
            search in path_piece
            for path_piece in SETTINGS[key]
        ):
            return _error(f'settings: "{key}" must have "{search}"')

    return True

# ======================================================================


def read_template(path=None):
    """Read the template definitions file.

    Args:
        path (Optional[str]): A path to the template definitions file to
            use instead.
            Default is None (use the settings file).

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

    # no required fields

    # add defaults if missing
    for level, level_defaults in FILES[key].items():
        level_values = raw_values.get(level, {})
        values[level] = {}
        for k, default in level_defaults.items():
            values[level][k] = level_values.get(k, default)

    # default bar count must be positive
    if values['values']['defaultBarCount'] <= 0:
        return _error(f'{key}: "defaultBarCount" must be positive')
    # notes row height must be at least 21
    if values['values']['notesRowHeight'] < 21:
        return _error(f'{key}: "notesRowHeight" must be at least 21')

    return True, values

# ======================================================================


def read_definitions(template_path=None,
                     pieces_path=None,
                     volunteers_path=None,
                     strict=False,
                     ):
    """Read the template file and the definitions files.
    Repeated pieces and volunteers will be combined.
    Unknown pieces for volunteers will be ignored.

    Args:
        template_path (Optional[str]): A path to the template
            definitions file to use instead.
            Default is None (use the settings file).
        pieces_path (Optional[str]): A path to the piece definitions
            file to use instead.
            Default is None (use the settings file).
        volunteers_path (Optional[str]): A path to the volunteer
            definitions file to use instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.

    Returns:
        Tuple[bool, Dict, Dict[str, Piece], Dict[str, Volunteer]]:
            Whether the read was successful,
            the template settings,
            a mapping from piece names to piece objects, and
            a mapping from volunteer emails to volunteer objects.
    """
    # FIXME: also write to file with fixed things
    #   e.g.: combine pieces, combine volunteers, remove duplicates

    ERROR_RETURN = False, None, None, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    success = _read_settings()
    if not success:
        return ERROR_RETURN

    success, template = read_template(template_path)
    if not success:
        return ERROR_RETURN

    logger.info('Reading piece definitions file')
    try:
        raw_pieces = _read_json('pieces', pieces_path)
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
            logger.debug(f'Combining piece "{name}"')
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

    logger.info('Reading volunteer definitions file')
    try:
        raw_volunteers = _read_json('volunteers', volunteers_path)
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
            logger.debug(f'Combining volunteer "{email}"')
            volunteers[email].combine(volunteer)
        else:
            volunteers[email] = volunteer

        for piece in volunteer.unknown_pieces:
            unknown_pieces = True
            logger.warning(f'volunteer {i}: unknown piece "{piece}"')
    if strict and unknown_pieces:
        fail_on_warning()
        return ERROR_RETURN

    # check that all volunteers have pieces
    invalid = False
    for volunteer in volunteers.values():
        if len(volunteer.pieces) == 0:
            invalid = True
            _error(f'volunteer "{volunteer.email}": no pieces found')
    if invalid:
        return ERROR_RETURN

    return True, template, pieces, volunteers

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


def read_volunteer_data(fmt_path=None):
    """Read volunteer data from files.

    Args:
        fmt_path (Optional[str]): A format path for volunteer data to
            use instead.
            Default is None (use the settings file).

    Returns:
        Tuple[bool, Dict[str, Dict]]: Whether the read was successful,
            and a mapping from volunteer emails to data.
    """
    ERROR_RETURN = False, None

    def _error(msg):
        return error(msg, ERROR_RETURN)

    success = _read_settings()
    if not success:
        return False

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

    logger.info(f'Reading volunteer data from files: {path}')

    path = path.resolve()

    # email -> file content
    files = {}
    for filepath in Path('.').glob('**/*'):
        if not filepath.is_file():
            continue
        filepath = filepath.resolve()
        if len(filepath.parts) != len(path.parts):
            continue
        found_email = None
        invalid = False
        for path_part, part in zip(path.parts, filepath.parts):
            if '{email}' in path_part:
                match = re.match(
                    path_part.replace('{email}', '(.+)'), part
                )
                if match is None:
                    invalid = True
                    break
                found_email = match.groups()[0]
            elif path_part != part:
                invalid = True
                break
        if invalid or found_email is None:
            continue
        files[found_email] = _read_json('', str(filepath))

    if len(files) == 0:
        logger.info('No matching files found')
        return ERROR_RETURN

    return True, files


def write_volunteer_data(data, fmt_path=None):
    """Write volunteer data to files.
    Replaces files if they already exist.

    Args:
        data (Dict[str, Dict]): A mapping from volunteer emails to data.
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

    logger.info(f'Writing volunteer data to files: {path}')

    for email, volunteer_data in data.items():
        _write_json_file(path.format(email=email), volunteer_data)

    return True

# ======================================================================


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

    logger.info(f'Writing piece data to files: {path}')

    for piece, piece_data in data.items():
        _write_json_file(path.format(piece=piece), piece_data)

    return True
