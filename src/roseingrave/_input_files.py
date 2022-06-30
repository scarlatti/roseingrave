"""
_input_files.py
Handles input files.
"""

# ======================================================================

from loguru import logger

from ._shared import fail_on_warning, error
from ._read_write import (
    _read_default,
    read_json,
    write_json,
    read_settings,
)
from ._piece import Piece
from ._piece_data import PieceData
from ._volunteer import Volunteer

# ======================================================================

__all__ = (
    'read_template',
    'read_piece_definitions', 'fix_piece_definitions',
    'read_volunteer_definitions', 'fix_volunteer_definitions',
)

# ======================================================================

# the options for the "publicAccess" field
PUBLIC_ACCESS_OPTIONS = (None, 'view', 'edit')


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

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('Reading template definitions file')

    key = 'template'

    try:
        raw_values = read_json(key, path)
    except (FileNotFoundError, ValueError) as ex:
        return _error(ex)
    defaults = _read_default('template_definitions.json')
    values = {
        level: {**level_defaults}
        for level, level_defaults in defaults.items()
    }
    invalid = False
    warning = False

    # no required fields

    # get values from file
    for level, level_values in raw_values.items():
        if level == 'validation':
            continue
        if level not in values:
            warning = True
            logger.warning('unknown key "{}"', level)
            continue
        level_defaults = values[level]
        for k, value in level_values.items():
            if k not in level_defaults:
                warning = True
                logger.warning('unknown key "{}"."{}"', level, k)
                continue
            level_defaults[k] = value
    # validation
    values['validation'] = {}
    for k, validation in raw_values.get('validation', {}).items():
        if k not in values['metaDataFields']:
            warning = True
            logger.warning('"validation": unknown key "{}"', k)
            continue
        if 'type' not in validation:
            warning = True
            logger.warning('"validation"."{}": no type', k)
            continue
        v_type = validation['type']
        if v_type == 'checkbox':
            values['validation'][k] = {'type': 'checkbox'}
        elif v_type == 'dropdown':
            if len(validation.get('values', [])) == 0:
                warning = True
                logger.warning(
                    '"validation"."{}": no values for dropdown', k
                )
                continue
            values['validation'][k] = {
                'type': 'dropdown',
                'values': validation['values'],
            }
        else:
            warning = True
            logger.warning(
                '"validation"."{}"."type": unknown type "{}"', k, v_type
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
            values[ss]['publicAccess'] = defaults[ss]['publicAccess']
    # volunteer spreadsheet title must have "{email}" at most once
    ss = 'volunteerSpreadsheet'
    if values[ss]['title'].count('{email}') > 1:
        invalid = True
        _error(
            f'"{ss}"."title": can only contain "{{email}}" at most once'
        )
    # must be a boolean
    for k in ('shareWithVolunteer', 'resize'):
        val = values[ss][k]
        if val not in (True, False):
            warning = True
            logger.warning(
                '"{}"."{}": invalid value "{}" (must be true or false)',
                ss, k, val
            )
            # reset to default
            values[ss][k] = defaults[ss][k]
    # default bar count must be positive
    if values['values']['defaultBarCount'] <= 0:
        invalid = True
        _error('"values"."defaultBarCount": must be positive')
    # comments row height must be at least 21
    if values['values']['commentsRowHeight'] < 21:
        invalid = True
        _error('"values"."commentsRowHeight": must be at least 21')

    if invalid:
        return ERROR_RETURN
    if strict and warning:
        fail_on_warning()
        return ERROR_RETURN

    return True, values

# ======================================================================


def _piece_definitions(path, template, msg):
    """Read the piece definitions file.
    Returns whether successful, whether there were pieces with no
    sources, the pieces with at least one source, and the pieces that
    only have supplemental sources.
    """
    ERROR_RETURN = False, None, None, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('{} piece definitions file', msg)

    try:
        raw_pieces = read_json('pieces', path)
    except (FileNotFoundError, ValueError) as ex:
        return _error(ex)
    if len(raw_pieces) == 0:
        return _error('no pieces found')

    pieces = {}
    for i, args in enumerate(raw_pieces):
        try:
            piece = Piece(args, template)
        except ValueError as ex:
            return _error('piece {}: {}', i, ex)

        name = piece.name
        if name in pieces:
            # combine sources with previous piece
            logger.debug('Combining piece "{}"', name)
            pieces[name].combine(piece)
        else:
            pieces[name] = piece

    filtered = {}
    only_supplemental = {}
    no_sources = False
    for title, piece in pieces.items():
        if piece.only_supplemental:
            logger.warning(
                'piece "{}": only supplemental sources found', title
            )
            only_supplemental[title] = piece
            continue
        if len(piece.sources) == 0:
            no_sources = True
            _error('piece "{}": no sources found', title)
            continue
        filtered[title] = piece

    return True, no_sources, filtered, only_supplemental


def read_piece_definitions(template,
                           path=None,
                           as_data=False,
                           as_both=False
                           ):
    """Read the piece definitions file.
    Repeated pieces and sources will be combined.
    All supplemental sources will be ignored, including pieces with only
    supplemental sources.

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

    success, no_sources, pieces, _ = _piece_definitions(
        path, template, msg='Reading'
    )
    if not success or no_sources:
        return False, None

    if as_both or as_data:
        pieces_data = {
            title: PieceData(piece)
            for title, piece in pieces.items()
        }
        if as_both:
            return True, (pieces, pieces_data)
        pieces = pieces_data

    return True, pieces


def fix_piece_definitions(path=None):
    """Fix the piece definitions file.
    Repeated pieces and sources will be combined.
    Supplemental sources will be moved to the end.
    Pieces with only supplemental sources will be moved to the end.

    Args:
        path (Optional[str]): A path to the piece definitions file to
            use instead.
            Default is None (use the settings file).

    Returns:
        Tuple[bool, Dict[str, Piece]]: Whether the fix was successful,
            and a mapping from piece names to piece objects.
    """
    ERROR_RETURN = False, None

    success, _, pieces, only_supplemental = _piece_definitions(
        path, None, msg='Fixing'
    )
    if not success:
        return ERROR_RETURN

    # add supplemental pieces to end
    for title, piece in only_supplemental.items():
        pieces[title] = piece

    if len(pieces) == 0:
        error('No valid pieces to write back to piece definitions file')
        return ERROR_RETURN

    data = [
        piece.to_json(include_supplemental=True)
        for piece in pieces.values()
    ]
    write_json(
        'pieces', data, path,
        msg='fixed piece definitions'
    )

    return True, pieces

# ======================================================================


def _volunteer_definitions(pieces, path, msg):
    """Read the volunteer definitions file.
    Ignores pieces that only had supplemental sources in the piece
    definitions file.
    Returns whether successful, whether there were volunteers with no
    pieces, whether there were unknown pieces, and the volunteers with
    at least one piece.
    """
    ERROR_RETURN = False, None, None, None

    def _error(msg, *args, **kwargs):
        return error(msg.format(*args, **kwargs), ERROR_RETURN)

    success = read_settings()
    if not success:
        return ERROR_RETURN

    logger.info('{} volunteer definitions file', msg)

    try:
        raw_volunteers = read_json('volunteers', path)
    except (FileNotFoundError, ValueError) as ex:
        return _error(ex)
    if len(raw_volunteers) == 0:
        return _error('no volunteers found')

    volunteers = {}
    unknown_pieces = False
    for i, args in enumerate(raw_volunteers):
        try:
            volunteer = Volunteer(args, pieces)
        except ValueError as ex:
            return _error('volunteer {}: {}', i, ex)

        email = volunteer.email
        if email in volunteers:
            # combine pieces with previous volunteer
            logger.debug('Combining volunteer "{}"', email)
            volunteers[email].combine(volunteer)
        else:
            volunteers[email] = volunteer

        for piece in volunteer.unknown_pieces:
            unknown_pieces = True
            logger.warning(
                'volunteer "{}": unknown piece "{}"', email, piece
            )

    filtered = {}
    no_pieces = False
    for email, volunteer in volunteers.items():
        if len(volunteer.pieces) == 0:
            no_pieces = True
            _error('volunteer "{}": no pieces found', email)
            continue
        filtered[email] = volunteer

    return True, no_pieces, unknown_pieces, filtered


def read_volunteer_definitions(pieces, path=None, strict=False):
    """Read the volunteer definitions file.
    Repeated volunteer emails will be combined.
    Unknown pieces and pieces with only supplemental sources will be
    ignored.

    Args:
        pieces (Dict[str, Piece]): The known pieces.
        path (Optional[str]): A path to the volunteer definitions file
            to use instead.
            Default is None (use the settings file).

    Returns:
        Tuple[bool, Dict[str, Volunteer]]:
            Whether the read was successful,
            and a mapping from volunteer emails to volunteer objects.
    """
    ERROR_RETURN = False, None

    success, no_pieces, unknown_pieces, volunteers = \
        _volunteer_definitions(pieces, path, msg='Reading')
    if not success or no_pieces:
        return ERROR_RETURN
    if strict and unknown_pieces:
        fail_on_warning()
        return ERROR_RETURN

    return True, volunteers


def fix_volunteer_definitions(pieces, path=None):
    """Fix the volunteer definitions file.
    Repeated volunteer emails will be combined.
    Pieces with only supplemental sources will be removed.

    Args:
        pieces (Dict[str, Piece]): The known pieces.
        path (Optional[str]): A path to the volunteer definitions file
            to use instead.
            Default is None (use the settings file).

    Returns:
        bool: Whether the fix was successful.
    """
    ERROR_RETURN = False

    success, _, _, volunteers = _volunteer_definitions(
        pieces, path, msg='Fixing'
    )
    if not success:
        return ERROR_RETURN

    if len(volunteers) == 0:
        error(
            'No valid volunteers to write back to volunteer '
            'definitions file'
        )
        return ERROR_RETURN

    data = [
        volunteer.to_json()
        for volunteer in volunteers.values()
    ]
    write_json(
        'volunteers', data, path,
        msg='fixed volunteer definitions'
    )

    return True
