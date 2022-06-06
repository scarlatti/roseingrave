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

    def __init__(self, piece, source):
        """Initialize the source data from a source.

        Args:
            piece (PieceData): The parent piece.
            source (Source): The source.
        """

        self._piece = piece

        self._name = source.name
        self._link = source.link
        self._volunteers = {}

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    def to_json(self, has_summary=False):
        """Return a JSON representation of this source data.

        Args:
            has_summary (bool): Whether this source data should contain
                a "summary" volunteer.
                Default is False.

        Returns:
            Dict: A JSON dict.
        """
        volunteers = self._volunteers
        if has_summary:
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

    def __init__(self, piece):
        """Initialize the piece data from a piece.

        Args:
            piece (Piece): The piece.
        """

        self._bar_count = piece.final_bar_count
        self._headers = list(piece._template['metaDataFields'].keys())

        self._name = piece.name
        self._link = piece.link
        self._sources = {
            source.name: SourceData(self, source)
            for source in piece.sources
        }
        self._notes = self.make_default(True)

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def bar_count(self):
        return self._bar_count

    def all_sources(self):
        """Return list of all source names."""
        return list(self._sources.keys())

    def has_source(self, name):
        """Check if this piece has a source with the given name."""
        return name in self._sources

    def get_source(self, name):
        """Get the source by the given name, or None."""
        return self._sources.get(name, None)

    def to_json(self, has_summary=False):
        """Return a JSON representation of this piece data.

        Args:
            has_summary (bool): Whether the source data should include
                a "summary" volunteer.
                Default is False.

        Returns:
            Dict: A JSON dict.
        """
        return {
            'title': self._name,
            'link': self._link,
            'sources': [
                source.to_json(has_summary)
                for source in self._sources.values()
            ],
            'notes': self._notes,
        }

    def make_default(self, is_notes=False):
        """Make a JSON dict with the default values."""

        if is_notes:
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
        # comments
        if not is_notes:
            values['comments'] = value()

        return values

    def with_defaults(self,
                      values,
                      loc,
                      exclude_comments=False,
                      is_notes=False
                      ):
        """Fix a JSON dict by adding the default values.
        Displays warnings for missing or extra fields.

        Args:
            values (Dict): The raw values.
            loc (str): The location, for warning messages.
            exclude_comments (bool): Whether to exclude the "comments"
                field.
                Default is False.
            is_notes (bool): Whether this dict is for "notes".
                Default is False.

        Returns:
            Tuple[bool, Dict]: Whether there was a warning,
                and the fixed dict.
        """

        fixed = self.make_default(is_notes)
        if exclude_comments:
            fixed.pop('comments', None)

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

        p_loc = f'volunteer "{email}", piece "{self._name}"'

        link = data['link']
        warning = False
        if self._link is None:
            if link is not None:
                warning = True
                logger.warning(
                    'Extra piece link "{}" for {}', link, p_loc
                )
        else:
            if link is None:
                warning = True
                logger.warning('Missing piece link for {}', p_loc)
            elif link != self._link:
                warning = True
                logger.warning(
                    'Incorrect piece link "{}" for {}', link, p_loc
                )
        if strict and warning:
            fail_on_warning()
            return False

        # sources
        for name, source in data['sources'].items():
            if name not in self._sources:
                logger.warning(
                    'Unknown source "{}" for {} '
                    '(not in piece definitions file)',
                    name, p_loc
                )
                if strict:
                    fail_on_warning()
                    return False
                continue
            self._sources[name].add_volunteer(email, source)

        # notes
        notes = data['notes']
        # special case: bars
        for bar_num, val in notes['bars'].items():
            if val == '':
                continue
            self._notes['bars'][bar_num][email] = val
        for key, val in notes.items():
            if key == 'bars':
                continue
            if val == '':
                continue
            self._notes[key][email] = val

        return True
