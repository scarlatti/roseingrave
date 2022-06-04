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

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def bar_count(self):
        return self._bar_count

    def combine(self, other):
        """Combine this source with another by taking max bar count."""
        self._bar_count = _max(self._bar_count, other.bar_count)

    def hyperlink(self):
        """Return a string formula for the linked source."""
        return _hyperlink(self._name, self._link)


class Piece:
    """Piece class."""

    def __init__(self, kwargs, template):
        """Initialize a piece from a JSON dict.

        Args:
            kwargs (Dict): The JSON dict.
            template (Dict): The template settings.

        Raises:
            ValueError: If any required key is not found.
            ValueError: If any source's bar count is not positive.
        """

        for key in ('title', 'sources'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._name = kwargs['title']
        self._link = kwargs.get('link', None)

        self._sources = {}
        self._bar_count = kwargs.get('barCount', None)
        for i, args in enumerate(kwargs['sources']):
            try:
                source = Source(args)
            except ValueError as ex:
                # re-raise the exception with added text
                ex.args = (f'source {i}: ' + ex.args[0],) + ex.args[1]
                raise
            self._add_source(source)

        self._template = template

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
            # notes row
            [template['commentFields']['notes']]
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

    def _add_source(self, source):
        """Add a source."""

        name = source.name
        if name in self._sources:
            logger.debug(
                'Combining source "{}" in piece "{}"',
                name, self._name
            )
            self._sources[name].combine(source)
        else:
            self._sources[name] = source

        self._bar_count = _max(self._bar_count, source.bar_count)

    def combine(self, other):
        """Combine this piece with another by combining all sources."""
        if self._link is None:
            self._link = other.link
        for source in other.sources:
            self._add_source(source)

    def has_source(self, name):
        """Check if this piece has a source with the given name."""
        return name in self._sources

    def get_source(self, name):
        """Get the source by the given name, or None."""
        return self._sources.get(name, None)

    def create_sheet(self, spreadsheet):
        """Create a sheet for this piece.

        Args:
            spreadsheet (gspread.Spreadsheet): The parent spreadsheet.

        Returns:
            gspread.Worksheet: The created sheet.
        """

        # add sheet
        sheet = spreadsheet.add_worksheet(self._name, 1, 1)

        # complete row 1
        row1 = [
            [_hyperlink(self._name, self._link)] +
            [source.hyperlink() for source in self._sources.values()] +
            [self._template['commentFields']['comments']]
        ]

        # update values with proper bar count
        bar_count = self._bar_count
        if bar_count is None:
            bar_count = self._template['values']['defaultBarCount']
        bars_section = [[i + 1] for i in range(bar_count)]

        values = row1 + self._values[0] + bars_section + self._values[1]

        # put the values
        sheet.update(values, raw=False)

        comments_col = len(row1[0])
        blank_row1 = 1 + len(self._values[0])  # row 1 + headers
        blank_row2 = blank_row1 + bar_count + 1
        notes_row = blank_row2 + 1

        _format_sheet(
            spreadsheet, sheet.id, self._template,
            comments_col, blank_row1, blank_row2, notes_row
        )

        return sheet

    @staticmethod
    def export_sheet(sheet, template):
        """Export piece data from a sheet.
        Assumes same format as a created sheet from
        `Piece.create_sheet()`.

        Args:
            sheet (gspread.Worksheet): The sheet.
            template (Dict): The template settings.

        Returns:
            Tuple[bool, Dict]: Whether the export was successful,
                and the data in JSON format.
        """

        values = sheet.get_values(value_render_option='formula')

        # row 1
        row1 = values[0]

        piece_link, piece_name = _parse_hyperlink(row1[0])
        if piece_name is None:
            piece_name = row1[0]

        headers = tuple(template['metaDataFields'].keys())

        headers_range = (1, 1 + len(headers))
        bars_range = (1 + len(headers) + 1, len(values) - 2)
        notes_row = len(values) - 1

        sources = []
        for col in range(1, len(row1) - 1):
            link, name = _parse_hyperlink(values[0][col])
            if link is None:
                col_letter = rowcol_to_a1(1, col+1)[:-1]
                error(
                    f'sheet "{sheet.title}": column {col_letter} '
                    'doesn\'t have a valid hyperlink'
                )
                return False, None

            source = {
                'name': name,
                'link': link,
            }

            for row, header in zip(range(*headers_range), headers):
                source[header] = values[row][col]

            bars_values = {}
            for row in range(*bars_range):
                bars_values[values[row][0]] = values[row][col]
            source['bars'] = bars_values

            source['notes'] = values[notes_row][col]

            sources.append(source)

        comments = {}
        for row, header in zip(range(*headers_range), headers):
            comments[header] = values[row][-1]
        bars_comments = {}
        for row in range(*bars_range):
            bars_comments[values[row][0]] = values[row][-1]
        comments['bars'] = bars_comments

        return True, {
            'title': piece_name,
            'link': piece_link,
            'sources': sources,
            'comments': comments,
        }

# ======================================================================


def _format_sheet(spreadsheet, sheet_id, template,
                  comments_col, blank_row1, blank_row2, notes_row):
    """Format a piece sheet."""

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

    requests = []

    # make everything middle aligned
    requests.append({
        'repeatCell': {
            'range': {'sheetId': sheet_id},
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
    centered_bolded = {
        'cell': {
            'userEnteredFormat': {
                'horizontalAlignment': 'CENTER',
                'textFormat': {'bold': True},
            },
        },
        'fields': ','.join((
            'userEnteredFormat.horizontalAlignment',
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
    source_end_column = rowcol_to_a1(1, comments_col - 1)
    comments_column = rowcol_to_a1(1, comments_col)[:-1]
    range_formats = (
        # piece name
        ('A1', bolded),
        # headers
        (f'A2:A{blank_row1 - 1}', bolded),
        # sources
        (f'B1:{source_end_column}', centered_bolded),
        # comments header
        (f'{comments_column}1', bolded),
        # notes header
        (f'A{notes_row}', bolded),
        # notes row
        (f'B{notes_row}:{notes_row}', wrapped_top_align),
    )
    for range_name, fmt in range_formats:
        requests.append({
            'repeatCell': {
                'range': gridrange(range_name, sheet_id=sheet_id),
                **fmt,
            }
        })

    range_borders = []

    # borders around empty rows
    # double border after the first row
    # double_border = {
    #     'style': 'DOUBLE',
    #     'color': BLACK,
    # }
    # range_borders += [
    #     ('1:1', {'bottom': double_border}),
    # ]

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

    # double border on the right of every column
    # for column in range(1, 1 + len(self._sources)):
    #     requests.append({
    #         'updateBorders': {
    #             'range': {
    #                 'sheetId': sheet_id,
    #                 'startColumnIndex': column,
    #                 'endColumnIndex': column + 1,
    #             },
    #             'right': double_border,
    #         }
    #     })

    column_widths = (
        # column 1: width 200
        ({'startIndex': 0, 'endIndex': 1}, 200),
        # all other columns: width 150
        ({'startIndex': 1}, 150),
    )
    for pos, width in column_widths:
        requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize': width,
                },
                'fields': 'pixelSize',
                'range': {
                    'sheet_id': sheet_id,
                    'dimension': 'COLUMNS',
                    **pos
                },
            }
        })

    # make notes row proper height
    requests.append({
        'updateDimensionProperties': {
            'properties': {
                'pixelSize': template['values']['notesRowHeight'],
            },
            'fields': 'pixelSize',
            'range': {
                'sheet_id': sheet_id,
                'dimension': 'ROWS',
                'startIndex': notes_row - 1,  # 0-indexed here
                'endIndex': notes_row,
            },
        }
    })

    # freeze row 1 and column 1
    requests.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'gridProperties': {
                    'frozenRowCount': 1,
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
    # don't include last column (comments)
    # don't include the last row (notes row)
    requests.append({
        'addBanding': {
            'bandedRange': {
                'range': {
                    'sheetId': sheet_id,
                    'startColumnIndex': 1,
                    'endColumnIndex': comments_col - 1,
                    'endRowIndex': notes_row - 1,
                },
                **white_gray_banding,
            },
        }
    })

    body = {'requests': requests}
    spreadsheet.batch_update(body)
