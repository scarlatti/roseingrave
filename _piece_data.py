"""
_piece_data.py
The PieceData and SourceData classes.
"""

# ======================================================================

from loguru import logger

from ._shared import fail_on_warning

# ======================================================================

__all__ = ('PieceData',)

# ======================================================================


class SourceData:
    """The data of a source from data files."""

    def __init__(self, piece, source, is_summary=False):
        """Initialize the source data from a source.

        Args:
            piece (PieceData): The parent piece.
            source (Source): The source.
            is_summary (bool): Whether this source data is for the
                summary of a piece.
                If True, an extra "summary" volunteer will be added.
                Default is False.
        """

        self._piece = piece
        self._is_summary = is_summary

        self._name = source.name
        self._link = source.link
        self._volunteers = {}

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    def to_json(self):
        """Return a JSON representation of this source data."""
        volunteers = self._volunteers
        if self._is_summary:
            volunteers['summary'] = self._piece.make_default()
        return {
            'name': self._name,
            'link': self._link,
            'volunteers': volunteers,
        }

    def add_volunteer(self, email, data):
        """Add a volunteer's data to this source.

        Args:
            email (str): The volunteer email.
            data (Dict): The volunteer data.

        Returns:
            bool: Whether the addition was successful.
        """
        self._volunteers[email] = {
            key: val for key, val in data.items()
            if key not in ('name', 'link')
        }


class PieceData:
    """The data of a piece from data files."""

    def __init__(self, piece, is_summary=False):
        """Initialize the piece data from a piece.

        Args:
            piece (Piece): The piece.
            is_summary (bool): Whether this piece data is for the
                summary of a piece.
                If True, all source data will have an extra "summary"
                volunteer.
                Default is False.
        """

        self._bar_count = piece.final_bar_count
        self._headers = list(piece._template['metaDataFields'].keys())

        self._name = piece.name
        self._link = piece.link
        self._sources = {
            source.name: SourceData(piece, source, is_summary)
            for source in piece.sources
        }
        self._comments = self.make_default(True)

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def bar_count(self):
        return self._bar_count

    def has_source(self, name):
        """Check if this piece has a source with the given name."""
        return name in self._sources

    def get_source(self, name):
        """Get the source by the given name, or None."""
        return self._sources.get(name, None)

    def to_json(self):
        """Return a JSON representation of this piece data."""
        return {
            'title': self._name,
            'link': self._link,
            'sources': [
                source.to_json()
                for source in self._sources.values()
            ],
            'comments': self._comments,
        }

    def make_default(self, is_comments=False):
        """Make a JSON dict with the default values."""

        if is_comments:
            def value():
                return {}
        else:
            def value():
                return ""

        # template names
        values = {key: value() for key in self._headers}
        # bars
        values['bars'] = {
            str(bar_num + 1): value()
            for bar_num in range(self._bar_count)
        }
        # notes
        if not is_comments:
            values['notes'] = value()

        return values

    def with_defaults(self, values, loc, is_comments=False):
        """Fix a JSON dict by adding the default values.
        Displays warnings for missing or extra fields.

        Args:
            values (Dict): The raw values.
            loc (str): The location, for warning messages.
            is_comments (bool): Whether this dict is for "comments".
                Excludes the "notes" field.
                Default is False.

        Returns:
            Tuple[bool, Dict]: Whether there was a warning,
                and the fixed dict.
        """

        fixed = self.make_default()
        if is_comments:
            fixed.pop('notes')

        extra_bars = []
        missing_bars = {}
        unknown_fields = []
        missing_fields = {key: True for key in fixed.keys()}

        # special case: bars
        if 'bars' in values:
            missing_fields.pop('bars')
            fixed_bars = fixed['bars']
            missing_bars = {
                bar_num: True for bar_num in fixed_bars.keys()
            }
            for bar_num, val in values['bars'].items():
                if bar_num not in fixed_bars:
                    extra_bars.append(bar_num)
                    continue
                missing_bars.pop(bar_num)
                fixed_bars[bar_num] = val
        # save all fields except for name, link, and bars
        for key, val in values.items():
            if key in ('name', 'link', 'bars'):
                continue
            if key not in fixed:
                unknown_fields.append(key)
                continue
            missing_fields.pop(key)
            fixed[key] = val

        warning = False

        # warn about missing fields
        if len(missing_fields) > 0:
            warning = True
            logger.warning(
                'Missing fields {} for {}',
                ','.join(f'"{key}"' for key in missing_fields.keys()),
                loc
            )
        if len(missing_bars) > 0:
            warning = True
            logger.warning(
                'Missing bar numbers {} for {}',
                ','.join(missing_bars.keys()), loc
            )

        # warn about extra fields
        if len(extra_bars) > 0:
            warning = True
            logger.warning(
                'Extra bars {} for {} (not in range of 1-{})',
                ','.join(extra_bars), loc, self._bar_count
            )
        if len(unknown_fields) > 0:
            warning = True
            logger.warning(
                'Unknown fields {} for {} '
                '(not in template definitions file)',
                ','.join(f'"{key}"' for key in unknown_fields), loc
            )

        return warning, fixed

    def add_volunteer(self, email, data, strict=False):
        """Add a volunteer's data to this piece.

        Args:
            email (str): The volunteer email.
            data (Dict): The volunteer data.
            strict (bool): Whether to fail on warnings instead of only
                displaying them.
                Default is False.

        Returns:
            bool: Whether the addition was successful.
        """

        # FIXME
        # if assume data from sheets is good, can update `self._link`
        # otherwise, treat piece definitions as absolute source of truth

        # sources
        for name, source in data['sources'].items():
            if name not in self._sources:
                logger.warning(
                    'Unknown source "{}" for volunteer "{}", '
                    'piece "{}" (not in piece definitions file)',
                    name, email, self._name
                )
                if strict:
                    fail_on_warning()
                    return False
                continue
            self._sources[name].add_volunteer(email, source)

        # comments
        comments = data['comments']
        # special case: bars
        for bar_num, val in comments['bars'].items():
            if val == '':
                continue
            self._comments['bars'][bar_num][email] = val
        for key, val in comments.items():
            if key == 'bars':
                continue
            if val == '':
                continue
            self._comments[key][email] = val

        return True
