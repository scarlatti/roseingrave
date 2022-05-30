"""
_shared.py
Shared constants and functions.
"""

# ======================================================================

import json
from pathlib import Path

import gspread
from loguru import logger

from ._piece import Piece
from ._volunteer import Volunteer

# ======================================================================

__all__ = (
    'fail_on_warning',
    'gspread_auth',
    'read_template', 'read_definitions',
    'read_spreadsheets_index', 'write_spreadsheets_index',
)

# ======================================================================

SETTINGS_FILE = 'roseingrave.json'

# every time the script is run, this gets populated for that run
SETTINGS = {}

# required fields and default values for input files
FILES = {
    'settings': {
        # the default settings
        'credentials': 'service_account.json',
        'definitionFiles': {
            'template': ['input', 'template_definitions.json'],
            'pieces': ['input', 'piece_definitions.json'],
            'volunteers': ['input', 'volunteer_definitions.json'],
        },
        'outputs': {
            'spreadsheetsIndex': ['output', 'spreadsheets.json'],
            'pieceSummary': ['output', 'summary.json'],
            'pieceDataPath': [
                'output', 'data', 'by-piece', '{piece}.json'
            ],
            'volunteerDataPath': [
                'output', 'data', 'by-volunteer', '{email}.json'
            ],
        },
    },
    'template': {
        'required': (
            'owner',
        ),
        'defaults': {
            'metaDataFields': {
                'title': 'Title',
                'tempo': 'Tempo',
                'key': 'Key',
                'keySig': 'Key sig.',
                'timeSig': 'Time sig.',
                'barCount': 'Bars',
                'compass': 'Compass',
                'comments': 'Comments',
                'notes': 'Notes',
                'clefs': 'Clefs (if other than G and F)',
                'endOrRepeat': 'Endings and Repeat signs',
                'articulation': 'Articulation signs',
                'dynamic': 'Dynamic signs',
                'hand': 'Hand signs',
                'otherIndications': 'Other indications',
            },
            'values': {
                'defaultBarCount': 100,
                'notesRowHeight': 75,
            },
        },
    },
}

# ======================================================================


def fail_on_warning():
    logger.error('Please fix warnings and run again.')

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

    filepath = Path(*path)
    if must_exist and not filepath.exists():
        raise FileNotFoundError(f'file "{filepath}" not found')
    if create_dirs:
        filepath.parent.mkdir(parents=True, exist_ok=True)
    return filepath


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
    if msg is not None:
        logger.info(f'Writing {msg} to "{filepath}"')
    filepath.write_text(json.dumps(data, indent=2), encoding='utf-8')

# ======================================================================


def _read_settings():
    """Read the settings file and update the `SETTINGS` global variable.
    """

    if len(SETTINGS) > 0:
        return

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

# ======================================================================


def gspread_auth():
    """Authenticate gspread to connect with Google Sheets.

    Returns:
        Tuple[bool, gspread.Client]: Whether the setup was successful,
            and the client.
    """
    _read_settings()

    logger.info('Setting up gspread authentication')
    filepath = Path(*SETTINGS['credentials'])
    if not filepath.exists():
        logger.error(f'file "{filepath}" not found')
        return False, None

    # service account
    client = gspread.service_account(str(filepath))

    # oauth
    # auth_user_path = Path(*SETTINGS['authorized_user'])
    # client = gspread.oauth(
    #     credentials_filename=str(filepath),
    #     authorized_user_filename=str(auth_user_path)
    # )

    return True, client

# ======================================================================


def _read_with_defaults(key, path=None):
    """Read data from a JSON file.
    Check for required fields and add default values.

    Args:
        key (str): The key representing the file.
        path (Optional[str]): A path to the file to use instead.
            Default is None (use the settings file).

    Raises:
        ValueError: If `path` is None and the key is invalid.
        FileNotFoundError: If the file is not found.
        ValueError: If any required key is not found.

    Returns:
        Dict[str, Any]: The contents of the JSON file.
    """
    _read_settings()

    raw_values = _read_json(key, path)
    values = {}

    # check required
    for k in FILES[key]['required']:
        if k not in raw_values:
            raise ValueError(f'{key}: key "{k}" not found')
        values[k] = raw_values[k]

    # add defaults if missing
    for k, default in FILES[key]['defaults'].items():
        values[k] = raw_values.get(k, default)

    return values

# ======================================================================


def read_template(path=None):
    """Read the template definition file.

    Args:
        path (Optional[str]): A path to the template definition file to
            use instead.
            Default is None (use the settings file).

    Returns:
        bool, Dict: Whether the read was successful,
            and the template settings.
    """
    logger.info('Reading template definition file')

    _read_settings()

    def error(msg):
        logger.error(msg)
        return False, None

    key = 'template'

    try:
        raw_values = _read_json(key, path)
    except FileNotFoundError as ex:
        return error(ex)
    values = {}

    # check required
    for k in FILES[key]['required']:
        if k not in raw_values:
            return error(f'{key}: key "{k}" not found')
        values[k] = raw_values[k]

    # add defaults if missing
    defaults = FILES[key]['defaults']
    for level in ('metaDataFields', 'values'):
        level_values = raw_values.get(level, {})
        values[level] = {}
        for k, default in defaults[level].items():
            values[level][k] = level_values.get(k, default)

    # default bar count must be positive
    if values['values']['defaultBarCount'] <= 0:
        return error(f'{key}: "defaultBarCount" must be positive')
    # notes row height must be at least 21
    if values['values']['notesRowHeight'] < 21:
        return error(f'{key}: "notesRowHeight" must be at least 21')

    return True, values


def read_definitions(template_path=None,
                     pieces_path=None,
                     volunteers_path=None,
                     strict=False,
                     ):
    """Read the definition files.
    Repeated pieces and volunteers will be combined.
    Unknown pieces for volunteers will be ignored.

    Args:
        template_path (Optional[str]): A path to the template definition
            file to use instead.
            Default is None (use the settings file).
        pieces_path (Optional[str]): A path to the piece definition file
            to use instead.
            Default is None (use the settings file).
        volunteers_path (Optional[str]): A path to the volunteer
            definition file to use instead.
            Default is None (use the settings file).
        strict (bool): Whether to fail on warnings instead of only
            displaying them.
            Default is False.

    Raises:
        FileNotFoundError: If any definition file is not found.

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

    _read_settings()

    success, template = read_template(template_path)
    if not success:
        return ERROR_RETURN

    def error(msg):
        logger.error(msg)
        return ERROR_RETURN

    logger.info('Reading piece definition file')
    try:
        raw_pieces = _read_json('pieces', pieces_path)
    except FileNotFoundError as ex:
        return error(ex)
    if len(raw_pieces) == 0:
        return error('no pieces found')

    pieces = {}
    for i, args in enumerate(raw_pieces):
        try:
            piece = Piece(args, template)
        except ValueError as ex:
            return error(f'piece {i}: {ex}')

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
            logger.error(f'piece "{piece.name}": no sources found')
    if invalid:
        return ERROR_RETURN

    logger.info('Reading volunteer definition file')
    try:
        raw_volunteers = _read_json('volunteers', volunteers_path)
    except FileNotFoundError as ex:
        return error(ex)
    if len(raw_volunteers) == 0:
        return error('no volunteers found')

    volunteers = {}
    unknown_pieces = False
    for i, args in enumerate(raw_volunteers):
        try:
            volunteer = Volunteer(args, pieces)
        except ValueError as ex:
            return error(f'volunteer {i}: {ex}')

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
            logger.error(
                f'volunteer "{volunteer.email}": no pieces found'
            )
    if invalid:
        return ERROR_RETURN

    return True, template, pieces, volunteers


def read_spreadsheets_index(path=None):
    """Read the spreadsheets index file.

    Args:
        path (Optional[str]): A path to the spreadsheets index file to
            use instead.
            Default is None (use the settings file).

    Returns:
        Dict[str, str]: A mapping from volunteer emails to spreadsheet
            links, or an empty dict if the file does not exist.
    """
    _read_settings()

    logger.info('Reading spreadsheets index file')
    try:
        return _read_json('spreadsheetsIndex', path)
    except FileNotFoundError:
        return {}

# ======================================================================


def write_spreadsheets_index(data, path=None):
    """Write to the spreadsheets index file.
    Updates the file if it exists, or creates it if it doesn't exist.

    Args:
        data (Dict[str, str]): The mapping from volunteer emails to
            spreadsheet links.
        path (Optional[str]): A path to the spreadsheets index file to
            use instead.
            Default is None (use the settings file).
    """
    _write_json(
        'spreadsheetsIndex', data, path,
        msg='created spreadsheet links'
    )
