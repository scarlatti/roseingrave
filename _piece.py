"""
_piece.py
The Piece and Source classes.
"""

# ======================================================================

import re

from gspread.utils import (
    a1_range_to_grid_range as gridrange,
    rowcol_to_a1,
)
from loguru import logger

from ._shared import error

# ======================================================================

__all__ = ('Piece',)

# ======================================================================

HYPERLINK_RE = re.compile(r'=HYPERLINK\("(.+)", "(.+)"\)')

# ======================================================================


def _col_str(col):
    """Return the column string of a column number (1-indexed)."""
    return rowcol_to_a1(1, col)[:-1]

# ======================================================================


def _hyperlink(text, link=None):
    """Create a hyperlink formula with optional link.

    Args:
        text (str): The placeholder text.
        link (str): The link.

    Returns:
        str: The hyperlink formula.
    """

    if link is None:
        return text
    escaped = text.replace('"', '\\"')
    return f'=HYPERLINK("{link}", "{escaped}")'


def _parse_hyperlink(hyperlink):
    """Extract the link and text from a hyperlink formula.

    Args:
        hyperlink (str): The hyperlink formula.

    Returns:
        Union[Tuple[str, str], Tuple[None, None]]:
            The link and the text, or None and None if the hyperlink
            is invalid.
    """

    match = HYPERLINK_RE.match(hyperlink)
    if match is None:
        return None, None
    link, text = match.groups()
    return link, text.replace('\\"', '"')


# ======================================================================

def _max(a, b):
    """Find the max of two possibly-None values."""
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)

# ======================================================================


class Source:
    """Source class."""

    def __init__(self, kwargs):
        """Initialize a source from a JSON dict.

        Args:
            kwargs (Dict): The JSON dict.

        Raises:
            ValueError: If any required key is not found.
            ValueError: If the bar count is not positive.
        """

        for key in ('name', 'link'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._name = kwargs['name']
        self._link = kwargs['link']
        self._bar_count = kwargs.get('barCount', None)
        # only allow positive bar counts
        if self._bar_count is not None and self._bar_count <= 0:
            raise ValueError('bar count must be positive')
        self._is_supplemental = kwargs.get('supplemental', False)

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def bar_count(self):
        return self._bar_count

    @property
    def is_supplemental(self):
        return self._is_supplemental

    def combine(self, other):
        """Combine this source with another by taking max bar count."""
        if self._link != other.link:
            logger.warning('Differing link: "{}"', other.link)
        self._bar_count = _max(self._bar_count, other.bar_count)
        if not self._is_supplemental:
            self._is_supplemental = other.is_supplemental

    def to_json(self, include_supplemental=False):
        """Return a JSON representation of this source."""
        values = {
            'name': self._name,
            'link': self._link,
        }
        if self._bar_count is not None:
            values['barCount'] = self._bar_count
        if include_supplemental and self._is_supplemental:
            values['supplemental'] = True
        return values

    def hyperlink(self):
        """Return a string formula for the linked source."""
        return _hyperlink(self._name, self._link)


class Piece:
    """Piece class."""

    def __init__(self, kwargs, template=None):
        """Initialize a piece from a JSON dict.

        Args:
            kwargs (Dict): The JSON dict.
            template (Optional[Dict]): The template settings.
                If None, only represents a piece; cannot do anything
                with it (such as create a sheet).

        Raises:
            ValueError: If any required key is not found.
            ValueError: If any source's bar count is not positive.
        """

        for key in ('title', 'sources'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._name = kwargs['title']
        self._link = kwargs.get('link', None)
        self._initial_bar_count = kwargs.get('barCount', None)

        sources = []
        for i, args in enumerate(kwargs['sources']):
            try:
                source = Source(args)
            except ValueError as ex:
                # re-raise the exception with added text
                ex.args = (f'source {i}: ' + ex.args[0],) + ex.args[1]
                raise
            sources.append(source)

        self._only_supplemental = False
        self._sources = {}
        self._supplemental_sources = {}
        self._bar_count = None
        self._add_sources(sources)

        self._template = template

        if self._template is None:
            self._values = None
            return

        # row 1 in `create_sheet()`

        before_bars = []
        # all other rows from template
        before_bars += [
            [header]
            for header in template['metaDataFields'].values()
        ]
        # empty row
        before_bars.append([])

        # bars section goes here

        after_bars = [
            # empty row
            [],
            # comments row
            [template['commentFields']['comments']]
        ]

        # before bar section, after bar section
        self._values = [before_bars, after_bars]

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def sources(self):
        return list(self._sources.values())

    @property
    def final_bar_count(self):
        if self._bar_count is None:
            return self._template['values']['defaultBarCount']
        return self._bar_count

    @property
    def only_supplemental(self):
        return self._only_supplemental

    def _add_sources(self, sources):
        """Add sources."""

        # add all sources
        for source in sources:
            name = source.name
            if name in self._sources:
                logger.debug(
                    'Combining source "{}" in piece "{}"',
                    name, self._name
                )
                existing_source = self._sources[name]
                existing_source.combine(source)
                if existing_source.is_supplemental:
                    self._supplemental_sources[name] = existing_source
                    self._sources.pop(name)
                continue
            if name in self._supplemental_sources:
                logger.debug(
                    'Combining source "{}" in piece "{}"',
                    name, self._name
                )
                self._supplemental_sources[name].combine(source)
                continue
            if source.is_supplemental:
                self._supplemental_sources[name] = source
            else:
                self._sources[name] = source

        # ignore this piece if there are only supplemental sources
        self._only_supplemental = (
            len(self._sources) == 0 and
            len(self._supplemental_sources) > 0
        )

        # re-calculate bar count with non-supplemental sources
        self._bar_count = self._initial_bar_count
        for source in self._sources.values():
            self._bar_count = _max(self._bar_count, source.bar_count)

    def combine(self, other):
        """Combine this piece with another by combining all sources."""
        if self._link is None:
            self._link = other.link
        elif other.link is None:
            logger.warning('Missing link')
        elif self._link != other.link:
            logger.warning('Differing link: "{}"', other.link)

        if self._initial_bar_count is None:
            # pylint: disable=protected-access
            self._initial_bar_count = other._initial_bar_count

        self._add_sources(other.sources)

    def has_source(self, name):
        """Check if this piece has a source with the given name."""
        return name in self._sources

    def get_source(self, name):
        """Get the source by the given name, or None."""
        return self._sources.get(name, None)

    def to_json(self, include_supplemental=False):
        """Return a JSON representation of this piece."""
        values = {}
        values['title'] = self._name
        if self._link is not None:
            values['link'] = self._link
        if self._initial_bar_count is not None:
            values['barCount'] = self.final_bar_count
        values['sources'] = [
            source.to_json()
            for source in self._sources.values()
        ]
        if include_supplemental:
            values['sources'] += [
                source.to_json(include_supplemental=True)
                for source in self._supplemental_sources.values()
            ]
        return values

    def _create_supplemental_sources_column(self, values, is_master):
        """Create the supplemental sources column(s) if needed.
        Wraps to more columns if there are too many sources.
        Return True if created.
        """
        if len(self._supplemental_sources) == 0:
            return False

        num_cols = len(values[0])
        start_row = 2 if is_master else 1
        # don't go into the comments row
        wrap_row = len(values) - 1

        values[0].append(
            self._template['commentFields']['supplementalSources']
        )

        row_index = start_row
        for source in self._supplemental_sources.values():
            row = values[row_index]
            if len(row) < num_cols:
                row += [''] * (num_cols - len(row))
            row.append(source.hyperlink())

            row_index += 1
            if row_index == wrap_row:
                # wrap back to top
                row_index = start_row

        return True

    def create_sheet(self, spreadsheet):
        """Create a sheet for this piece.

        Args:
            spreadsheet (gspread.Spreadsheet): The parent spreadsheet.

        Returns:
            gspread.Worksheet: The created sheet.
        """

        if self._template is None:
            raise RuntimeError(
                f'cannot create sheet for piece "{self._name}": '
                'no template given during creation'
            )

        # add sheet
        sheet = spreadsheet.add_worksheet(self._name, 1, 1)

        # complete row 1
        row1 = (
            [_hyperlink(self._name, self._link)] +
            [source.hyperlink() for source in self._sources.values()] +
            [self._template['commentFields']['notes']]
        )

        # proper bar count
        bar_count = self.final_bar_count

        values = [
            row1,
            # use copy of `self._values`
            *[row[:] for row in self._values[0]],
            *[[i + 1] for i in range(bar_count)],
            *[row[:] for row in self._values[1]],
        ]

        notes_col = len(values[0])
        blank_row1 = 1 + len(self._values[0])  # row 1 + headers
        blank_row2 = blank_row1 + bar_count + 1
        comments_row = blank_row2 + 1

        # to make sure columns are auto-resized with a minimum width,
        # insert text in every column, then remove it after formatting
        resize = self._template['volunteerSpreadsheet']['resize']
        if resize:
            values[blank_row1 - 1] = (
                # header column (202 pixels)
                ['placeholderplaceholderplaceh'] +
                # source columns (154 pixels)
                ['placeholderplaceholde'] * (len(values[0]) - 2)
            )

        has_supplemental_col = self._create_supplemental_sources_column(
            values, is_master=False
        )

        # put the values
        sheet.update(values, raw=False)

        _format_sheet(
            spreadsheet, sheet, self._template,
            notes_col, blank_row1, blank_row2, comments_row,
            resize=resize, has_supplemental_col=has_supplemental_col
        )

        if resize:
            start = f'A{blank_row1}'
            end = f'{_col_str(notes_col - 1)}{blank_row1}'
            sheet.batch_clear([f'{start}:{end}'])

        return sheet

    def create_master_sheet(self, spreadsheet, piece_data):
        """Create a sheet for the master spreadsheet.

        Args:
            spreadsheet (gspread.Spreadsheet): The master spreadsheet.
            piece_data (Dict): The data for the piece.

        Returns:
            gspread.Worksheet: The created sheet.
        """

        if self._template is None:
            raise RuntimeError(
                f'cannot create sheet for piece "{self._name}": '
                'no template given during creation'
            )

        # add sheet
        sheet = spreadsheet.add_worksheet(self._name, 1, 1)

        # proper bar count
        bar_count = self.final_bar_count

        # finish headers
        values = [
            [_hyperlink(self._name, self._link)],
            ['Volunteer'],
            # use copy of `self._values`
            *[row[:] for row in self._values[0]],
            *[[i + 1] for i in range(bar_count)],
            *[row[:] for row in self._values[1]],
        ]

        headers = tuple(self._template['metaDataFields'].keys())

        headers_start = 2
        headers_iter = [
            (headers_start + i, header)
            for i, header in enumerate(headers)
        ]

        blank_row1 = 2 + len(headers) + 1  # 2 rows + headers
        blank_row2 = blank_row1 + bar_count + 1
        comments_row = blank_row2 + 1

        bars_start = blank_row1
        bars_iter = [
            (bars_start + i, str(i + 1))
            for i in range(bar_count)
        ]

        # go through sources and add
        sources = piece_data['sources']
        # list of starting col number for each source (1-indexed)
        source_cols = []
        col = 2
        for name, source in self._sources.items():
            source_data = sources[name]
            source_cols.append(col)

            def add_column(email, volunteer):
                # row 1
                values[0].append('')
                # row 2
                values[1].append(email)
                # headers
                for row, header in headers_iter:
                    values[row].append(volunteer[header])
                # bars
                bars = volunteer['bars']
                for row, bar_num in bars_iter:
                    values[row].append(bars[bar_num])
                # comments
                values[comments_row - 1].append(volunteer['comments'])

            start_col = col - 1

            # volunteers
            for email, volunteer in source_data['volunteers'].items():
                add_column(email, volunteer)
                col += 1
            # summary
            add_column(
                self._template['commentFields']['summary'],
                source_data['summary']
            )
            col += 1

            # put the source hyperlink
            values[0][start_col] = source.hyperlink()

        # notes column
        notes_col = col

        def note_str(notes):
            return '\n'.join(
                f'{email}: {note}'
                for email, note in notes.items()
            )

        values[0].append(self._template['commentFields']['notes'])
        notes = piece_data['notes']
        for row, header in headers_iter:
            values[row].append(note_str(notes[header]))
        bars = notes['bars']
        for row, bar_num in bars_iter:
            values[row].append(note_str(bars[bar_num]))

        # force headers column to be 202 pixels minimum
        resize = self._template['masterSpreadsheet']['resize']
        if resize:
            values[blank_row1 - 1] = ['placeholderplaceholderplaceh']

        has_supplemental_col = self._create_supplemental_sources_column(
            values, is_master=True
        )

        # put the values
        sheet.update(values, raw=False)

        _format_sheet(
            spreadsheet, sheet, self._template,
            notes_col, blank_row1, blank_row2, comments_row,
            resize=resize, is_master=True, source_cols=source_cols,
            has_supplemental_col=has_supplemental_col
        )

        if resize:
            sheet.batch_clear([f'A{blank_row1}'])

        return sheet

    @staticmethod
    def export_sheet(sheet, template):
        """Export piece data from a sheet.
        Assumes same format as a created sheet from
        `Piece.create_sheet()`.
        Ignores the supplemental sources column if it exists.

        Args:
            sheet (gspread.Worksheet): The sheet.
            template (Dict): The template settings.

        Returns:
            Tuple[bool, Dict]: Whether the export was successful,
                and the data in JSON format.
        """
        ERROR_RETURN = False, None

        def _error(msg, *args, **kwargs):
            return error(msg.format(*args, **kwargs), ERROR_RETURN)

        (
            values,
            piece_link, piece_name,
            headers_iter, bars_iter,
            comments_row, notes_col,
        ) = _export_helper(sheet, template, is_master=True)

        def export_column(col, include_comments=True):
            column = {}
            for row, header in headers_iter:
                column[header] = values[row][col]
            bars = {}
            for row in bars_iter:
                bars[values[row][0]] = values[row][col]
            column['bars'] = bars
            if include_comments:
                column['comments'] = values[comments_row][col]
            return column

        sources = []
        for col in range(1, notes_col):
            link, name = _parse_hyperlink(values[0][col])
            if link is None:
                return _error(
                    'sheet "{}": column {} doesn\'t have a valid '
                    'hyperlink',
                    sheet.title, _col_str(col + 1)
                )

            source = {
                'name': name,
                'link': link,
                **export_column(col),
            }
            sources.append(source)

        notes = export_column(notes_col, False)

        return True, {
            'title': piece_name,
            'link': piece_link,
            'sources': sources,
            'notes': notes,
        }

    @staticmethod
    def export_master_sheet(sheet, template):
        """Export a sheet from the master spreadsheet.
        Assumes same format as a created sheet from
        `Piece.create_master_sheet()`.
        Assumes the last column for each source is the summary column.

        Args:
            sheet (gspread.Worksheet): The sheet.
            template (Dict): The template settings.

        Returns:
            Tuple[bool, Dict]: Whether the export was successful,
                and the data in JSON format.
        """
        ERROR_RETURN = False, None

        def _error(msg, *args, **kwargs):
            return error(msg.format(*args, **kwargs), ERROR_RETURN)

        (
            values,
            piece_link, piece_name,
            headers_iter, bars_iter,
            comments_row, notes_col,
        ) = _export_helper(sheet, template, is_master=True)

        sources = []
        curr_source = {}
        for col in range(1, notes_col):
            if values[0][col] != '':
                # new source
                link, name = _parse_hyperlink(values[0][col])
                if link is None:
                    return _error(
                        'sheet "{}": column {} doesn\'t have a valid '
                        'hyperlink',
                        sheet.title, _col_str(col + 1)
                    )

                curr_source = {
                    'name': name,
                    'link': link,
                    'volunteers': {},
                    'summary': None,
                }
                sources.append(curr_source)

            # always overwrite summary, pushing existing to volunteers
            email = values[1][col]

            column = {}
            for row, header in headers_iter:
                column[header] = values[row][col]
            bars = {}
            for row in bars_iter:
                bars[values[row][0]] = values[row][col]
            column['bars'] = bars
            column['comments'] = values[comments_row][col]

            if curr_source['summary'] is not None:
                # push to volunteers
                prev_email, prev_column = curr_source['summary']
                curr_source['volunteers'][prev_email] = prev_column
            # save to summary
            curr_source['summary'] = (email, column)

        # fix all summaries
        for source in sources:
            _, summary = source['summary']
            source['summary'] = summary

        def parse_note(note_str):
            note = {}
            for line in note_str.split('\n'):
                if line == '':
                    continue
                try:
                    email, text = line.split(': ', 1)
                    note[email] = text
                except ValueError:
                    logger.warning(
                        'Note line has invalid format: {}', line
                    )
            return note

        notes = {}
        for row, header in headers_iter:
            notes[header] = parse_note(values[row][notes_col])
        bars = {}
        for row in bars_iter:
            bars[values[row][0]] = parse_note(values[row][notes_col])
        notes['bars'] = bars

        return True, {
            'title': piece_name,
            'link': piece_link,
            'sources': sources,
            'notes': notes,
        }

# ======================================================================


def _format_sheet(spreadsheet, sheet, template,
                  notes_col, blank_row1, blank_row2, comments_row,
                  resize=False, is_master=False, source_cols=None,
                  has_supplemental_col=False
                  ):
    """Format a piece sheet."""

    sheet_id = sheet.id

    def hex_to_rgb(hex_color):
        """Changes a hex color code (no pound) to an RGB color dict.
        Each value is a fraction decimal instead of an integer.
        """
        colors = ('red', 'green', 'blue')
        return {
            key: int(hex_color[i:i+2], 16) / 255
            for key, i in zip(colors, range(0, 6, 2))
        }

    BLACK = hex_to_rgb('000000')

    header_end = 2 if is_master else 1

    if source_cols is None:
        source_cols = []
    source_cols.append(notes_col)

    requests = []

    # make everything except last (comments) row middle aligned
    requests.append({
        'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'endRowIndex': blank_row2 - 1,
            },
            'cell': {
                'userEnteredFormat': {
                    'verticalAlignment': 'MIDDLE',
                },
            },
            'fields': 'userEnteredFormat.verticalAlignment',
        }
    })

    # formatting
    bolded = {
        'cell': {
            'userEnteredFormat': {
                'textFormat': {'bold': True},
            },
        },
        'fields': 'userEnteredFormat.textFormat.bold',
    }
    centered = {
        'cell': {
            'userEnteredFormat': {
                'horizontalAlignment': 'CENTER',
            },
        },
        'fields': 'userEnteredFormat.horizontalAlignment',
    }
    middle_bolded = {
        'cell': {
            'userEnteredFormat': {
                'verticalAlignment': 'MIDDLE',
                'textFormat': {'bold': True},
            },
        },
        'fields': ','.join((
            'userEnteredFormat.verticalAlignment',
            'userEnteredFormat.textFormat.bold',
        ))
    }
    wrapped_top_align = {
        'cell': {
            'userEnteredFormat': {
                'wrapStrategy': 'WRAP',
                'verticalAlignment': 'TOP',
            },
        },
        'fields': ','.join((
            'userEnteredFormat.wrapStrategy',
            'userEnteredFormat.verticalAlignment',
        ))
    }
    source_end_column = _col_str(notes_col - 1)
    range_formats = [
        # first row (piece name, sources, notes, possible supplemental)
        ('A1:1', bolded),
        # headers
        (f'A2:A{blank_row1 - 1}', bolded),
        # sources
        (f'B1:{source_end_column}1', centered),
        # comments header
        (f'A{comments_row}', middle_bolded),
        # comments row
        (f'B{comments_row}:{comments_row}', wrapped_top_align),
    ]
    if is_master:
        # make all summary cells be centered
        center_align = {
            'cell': {
                'userEnteredFormat': {
                    'horizontalAlignment': 'CENTER',
                },
            },
            'fields': 'userEnteredFormat.horizontalAlignment',
        }
        range_formats += [
            (f'{_col_str(col - 1)}2', center_align)
            for col in source_cols[1:]
        ]
        # make volunteers line bolded
        range_formats += [
            (f'B2:{source_end_column}2', bolded),
        ]
    for range_name, fmt in range_formats:
        requests.append({
            'repeatCell': {
                'range': gridrange(range_name, sheet_id=sheet_id),
                **fmt,
            }
        })

    # borders
    range_borders = []

    if is_master:
        double_border = {
            'style': 'DOUBLE',
            'color': BLACK,
        }

        # double border after the header rows
        range_borders += [
            (f'{header_end}:{header_end}', {'bottom': double_border}),
        ]

        # double border before every source column
        left_double_border = {'left': double_border}
        for col in source_cols:
            col_str = _col_str(col)
            range_borders.append(
                (f'{col_str}:{col_str}', left_double_border)
            )

        # merge source columns
        for i in range(len(source_cols) - 1):
            requests.append({
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id,
                        # row 1
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        # between each source col (0-indexed)
                        'startColumnIndex': source_cols[i] - 1,
                        'endColumnIndex': source_cols[i + 1] - 1,
                    },
                    'mergeType': 'MERGE_ALL',
                }
            })

    # borders around empty rows
    solid_black = {
        'style': 'SOLID',
        'color': BLACK,
    }
    top_bottom_border = {
        'top': solid_black,
        'bottom': solid_black,
    }
    range_borders += [
        (f'A{blank_row1}:{blank_row1}', top_bottom_border),
        (f'A{blank_row2}:{blank_row2}', top_bottom_border),
    ]

    # dotted border after every fifth bar
    interval = 5
    bottom_dotted_border = {
        'bottom': {
            'style': 'DOTTED',
            'color': BLACK,
        }
    }
    range_borders += [
        (f'A{row}:{row}', bottom_dotted_border) for row in
        range(blank_row1 + interval, blank_row2 - 1, interval)
    ]

    for range_name, borders in range_borders:
        requests.append({
            'updateBorders': {
                'range': gridrange(range_name, sheet_id=sheet_id),
                **borders,
            }
        })

    column_widths = []
    if not resize:
        column_widths.append(
            # column 1: width 200
            ({'startIndex': 0, 'endIndex': 1}, 200),
        )
    if is_master or not resize:
        column_widths.append(
            # source columns: width 150
            ({'startIndex': 1, 'endIndex': notes_col - 1}, 150),
        )
    column_widths.append(
        # notes col: width 300
        ({'startIndex': notes_col - 1, 'endIndex': notes_col}, 300),
    )
    if has_supplemental_col:
        column_widths.append(
            # supplemental sources column(s): width of 150
            ({'startIndex': notes_col}, 150),
        )
    for pos, width in column_widths:
        requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize': width,
                },
                'fields': 'pixelSize',
                'range': {
                    'sheetId': sheet_id,
                    'dimension': 'COLUMNS',
                    **pos
                },
            }
        })

    if resize:
        end_col = 1 if is_master else (notes_col - 1)
        # auto-resize headers column and source columns
        requests.append({
            'autoResizeDimensions': {
                'dimensions': {
                    'sheetId': sheet_id,
                    'dimension': 'COLUMNS',
                    'startIndex': 0,
                    'endIndex': end_col,
                },
            }
        })

    # make comments row proper height
    requests.append({
        'updateDimensionProperties': {
            'properties': {
                'pixelSize': template['values']['commentsRowHeight'],
            },
            'fields': 'pixelSize',
            'range': {
                'sheetId': sheet_id,
                'dimension': 'ROWS',
                'startIndex': comments_row - 1,  # 0-indexed here
                'endIndex': comments_row,
            },
        }
    })

    # freeze header rows and column 1
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'gridProperties': {
                    'frozenRowCount': header_end,
                    'frozenColumnCount': 1,
                },
            },
            'fields': ','.join((
                'gridProperties.frozenRowCount',
                'gridProperties.frozenColumnCount',
            )),
        }
    })

    # default banding style white/gray
    white_gray_banding = {
        'rowProperties': {
            'headerColor': hex_to_rgb('bdbdbd'),
            'firstBandColor': hex_to_rgb('ffffff'),
            'secondBandColor': hex_to_rgb('f3f3f3'),
            # 'footerColor': hex_to_rgb('dedede'),
        },
    }
    # don't include last column (notes) or last row (comments)
    requests.append({
        'addBanding': {
            'bandedRange': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': 0,
                    'endRowIndex': comments_row - 1,
                    'startColumnIndex': 1,
                    'endColumnIndex': notes_col - 1,
                },
                **white_gray_banding,
            },
        }
    })

    # data validation
    header_rows = {
        header: header_end + i
        for i, header in enumerate(template['metaDataFields'].keys())
    }
    for key, validation in template['validation'].items():
        row = header_rows[key]
        v_type = validation['type']
        if v_type == 'checkbox':
            condition = {'type': 'BOOLEAN'}
        elif v_type == 'dropdown':
            condition = {
                'type': 'ONE_OF_LIST',
                'values': [
                    {'userEnteredValue': val}
                    for val in validation['values']
                ],
            }
        else:
            # shouldn't happen
            continue
        requests.append({
            'setDataValidation': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': row,
                    'endRowIndex': row + 1,
                    'startColumnIndex': 1,
                    'endColumnIndex': notes_col - 1,
                },
                'rule': {
                    'condition': condition,
                    'strict': False,
                    'showCustomUi': True,
                },
            }
        })

    body = {'requests': requests}
    spreadsheet.batch_update(body)

# ======================================================================


def _export_helper(sheet, template, is_master):
    """Export a sheet and get important helper values."""

    values = sheet.get_values(value_render_option='formula')

    # row 1
    row1 = values[0]

    piece_link, piece_name = _parse_hyperlink(row1[0])
    if piece_name is None:
        piece_name = row1[0]

    headers = tuple(template['metaDataFields'].keys())

    start_row = 2 if is_master else 1
    headers_range = (start_row, start_row + len(headers))
    headers_iter = list(zip(range(*headers_range), headers))

    bars_range = (start_row + len(headers) + 1, len(values) - 2)
    bars_iter = list(range(*bars_range))

    comments_row = len(values) - 1

    # skip over supplemental sources column
    notes_col = len(row1) - 1
    notes_col_title = template['commentFields']['notes']
    while notes_col >= 0 and row1[notes_col] != notes_col_title:
        notes_col -= 1
    if notes_col == -1:
        # not found, so assume it's the last column
        notes_col = len(row1) - 1

    return (
        values,
        piece_link, piece_name,
        headers_iter, bars_iter,
        comments_row, notes_col,
    )
