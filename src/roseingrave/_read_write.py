"""
_read_write.py
Read and write operations on files.
"""

# ======================================================================

import json
from pathlib import Path

from loguru import logger

from ._shared import error

# ======================================================================

__all__ = (
    'get_path',
    'read_json', 'write_json', 'write_json_file',
    'read_settings', 'fix_settings',
)

# ======================================================================

SETTINGS_FILE = 'roseingrave.json'

# every time the script is run, this gets populated for that run
# becomes flattened version of the file
SETTINGS = {}

# ======================================================================


def _read_default(file):
    """Read a default configuration from the "defaults" directory."""
    filepath = Path(Path(__file__).parent, 'defaults', file)
    contents = filepath.read_text(encoding='utf-8')
    return json.loads(contents)

# ======================================================================


def get_path(key, path=None, must_exist=True, create_dirs=False):
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


def read_json(key, path=None):
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
    filepath = get_path(key, path)
    contents = filepath.read_text(encoding='utf-8')
    return json.loads(contents)


def _write(filepath, data, msg):
    if msg is not None:
        logger.info('Writing {} to "{}"', msg, filepath)
    filepath.write_text(json.dumps(data, indent=2), encoding='utf-8')


def write_json(key, data, path=None, msg=None):
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
    filepath = get_path(key, path, must_exist=False, create_dirs=True)
    _write(filepath, data, msg)


def write_json_file(path, data, msg=None):
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


def _settings(msg, clear=False, must_exist=False):
    """Read the settings file and update the `SETTINGS` global variable.
    Returns whether successful and the fixed inputted settings.
    """
    ERROR_RETURN = False, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    if clear:
        SETTINGS.clear()
    if len(SETTINGS) > 0:
        return True, SETTINGS

    logger.info('{} settings file', msg)

    try:
        raw_values = read_json('', SETTINGS_FILE)
    except FileNotFoundError:
        if must_exist:
            _error('No settings file found to fix')
            return ERROR_RETURN
        # no settings file, so just use all defaults
        raw_values = {}

    # add defaults if missing
    defaults = _read_default('roseingrave.json')
    fixed = {}

    # credentials
    if 'credentials' in raw_values:
        fixed['credentials'] = raw_values['credentials']
        path = raw_values['credentials']
    else:
        path = defaults['credentials']
    if isinstance(path, str):  # turn into list if a str
        path = [path]
    SETTINGS['credentials'] = path
    SETTINGS['authorized_user'] = path[:-1] + ['authorized_user.json']

    for level, level_defaults in defaults.items():
        # already took care of credentials
        if level in ('credentials',):
            continue
        if level in raw_values:
            fixed[level] = {}
            fixed_level = fixed[level]
            values = raw_values[level]
        else:
            values = {}
        for k, default in level_defaults.items():
            if k in values:
                path = values[k]
                fixed_level[k] = path
            else:
                path = default
            if isinstance(path, str):  # turn into list if a str
                path = [path]
            SETTINGS[k] = path

    # validate values
    invalid = False
    for key, value in SETTINGS.items():
        if not value[-1].endswith('.json'):
            invalid = True
            _error('"{}" must be a ".json" file', key)
    for key, search in (
        ('volunteerDataPath', '{email}'),
        ('pieceDataPath', '{piece}'),
    ):
        count = sum(
            path_piece.count(search)
            for path_piece in SETTINGS[key]
        )
        if count != 1:
            invalid = True
            _error('"{}" must have "{}" exactly once', key, search)
    if invalid:
        return ERROR_RETURN

    return True, fixed


def read_settings():
    """Read the settings file.

    Returns:
        bool: Whether the read was successful.
    """
    success, _ = _settings('Reading')
    return success


def fix_settings():
    """Fix the settings file.

    Returns:
        bool: Whether the fix was successful.
    """
    success, fixed = _settings('Fixing', clear=True, must_exist=True)
    if not success:
        return False

    write_json(
        '', fixed, SETTINGS_FILE,
        msg='fixed settings file'
    )

    return True
