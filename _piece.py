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


class Source:
    """Source class."""

    def __init__(self, kwargs):
        """Initialize a source from a JSON dict.

        Args:
            kwargs (Dict): The JSON dict.

        Raises:
            ValueError: If any required key is not found.
        """

        for key in ('name', 'link'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._name = kwargs['name']
        self._link = kwargs['link']
        self._bar_count = kwargs.get('barCount', None)
        # only allow positive bar counts
        if self._bar_count is not None and self._bar_count <= 0:
            self._bar_count = None

    @property
    def name(self):
        return self._name

    @property
    def link(self):
        return self._link

    @property
    def bar_count(self):
        return self._bar_count

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
        """

        for key in ('title', 'sources'):
            if key not in kwargs:
                raise ValueError(f'key "{key}" not found')

        self._name = kwargs['title']
        self._link = kwargs.get('link', None)

        self._sources = []
        self._bar_count = None
        for i, args in enumerate(kwargs['sources']):
            try:
                source = Source(args)
            except ValueError as ex:
                # re-raise the exception with added text
                ex.args = (f'source{i}: ' + ex.args[0],) + ex.args[1]
                raise
            self._sources.append(source)
            bars = source.bar_count
            if bars is not None:
                if self._bar_count is None or bars > self._bar_count:
                    self._bar_count = bars

        self._template = template

        before_bars = []
        # row 1: piece name, source names, and comments column
        before_bars.append(
            # fill in with name in `create_sheet()`
            [''] +
            [source.hyperlink() for source in self._sources] +
            [template['commentFields']['comments']]
        )
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
        return self._sources

    def combine(self, other):
        """Combine this piece with another by combining all sources."""
        if self._link is None and other.link is not None:
            self._link = other.link
        for source in other.sources:
            self._sources.append(source)
            bars = source.bar_count
            if bars is not None:
                if self._bar_count is None or bars > self._bar_count:
                    self._bar_count = bars

    def create_sheet(self, spreadsheet):
        """Create a sheet for this piece.

        Args:
            spreadsheet (gspread.Spreadsheet): The parent spreadsheet.

        Returns:
            gspread.Worksheet: The created sheet.
        """

        # add sheet
        sheet = spreadsheet.add_worksheet(self._name, 1, 1)

        # update name with optional link
        self._values[0][0][0] = _hyperlink(self._name, self._link)

        # update values with proper bar count
        bar_count = self._bar_count
        if bar_count is None:
            bar_count = self._template['values']['defaultBarCount']
        bars_section = [[i + 1] for i in range(bar_count)]

        values = self._values[0] + bars_section + self._values[1]

        # put the values
        sheet.update(values, raw=False)

        requests = []

        blank_row1 = len(self._values[0])
        blank_row2 = blank_row1 + bar_count + 1
        notes_row = blank_row2 + 1

        # make everything middle aligned
        requests.append({
            'repeatCell': {
                'range': {'sheetId': sheet.id},
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
        range_formats = (
            # template row headers
            (f'A2:A{blank_row1 - 1}', bolded),
            # sources
            ('A1:1', bolded),
            # notes header
            (f'A{notes_row}', bolded),
            # notes row
            (f'B{notes_row}:{notes_row}', wrapped_top_align),
        )

        for range_name, fmt in range_formats:
            requests.append({
                'repeatCell': {
                    'range': gridrange(range_name, sheet_id=sheet.id),
                    **fmt,
                }
            })

        # borders around empty rows
        solid_black = {
            'style': 'SOLID',
            'color': {'red': 0, 'green': 0, 'blue': 0},
        }
        top_bottom_border = {
            'top': solid_black,
            'bottom': solid_black,
        }
        range_borders = (
            (f'A{blank_row1}:{blank_row1}', top_bottom_border),
            (f'A{blank_row2}:{blank_row2}', top_bottom_border),
        )

        # dotted border after every fifth bar
        interval = 5
        bottom_dotted_border = {
            'bottom': {
                'style': 'DOTTED',
                'color': {'red': 0, 'green': 0, 'blue': 0},
            }
        }
        range_borders += tuple(
            (f'A{row}:{row}', bottom_dotted_border) for row in
            range(blank_row1 + interval, blank_row2 - 1, interval)
        )

        # double border after the first row
        # double_border = {
        #     'style': 'DOUBLE',
        #     'color': {'red': 0, 'green': 0, 'blue': 0},
        # }
        # range_borders += (('1:1', {'bottom': double_border}),)

        for range_name, borders in range_borders:
            requests.append({
                'updateBorders': {
                    'range': gridrange(range_name, sheet_id=sheet.id),
                    **borders,
                }
            })

        # double border on the right of every column
        # for column in range(1, 1 + len(self._sources)):
        #     requests.append({
        #         'updateBorders': {
        #             'range': {
        #                 'sheetId': sheet.id,
        #                 'startColumnIndex': column,
        #                 'endColumnIndex': column + 1,
        #             },
        #             'right': double_border,
        #         }
        #     })

        # make column 1 width 200
        requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize': 200,
                },
                'fields': 'pixelSize',
                'range': {
                    'sheet_id': sheet.id,
                    'dimension': 'COLUMNS',
                    'startIndex': 0,
                    'endIndex': 1,
                },
            }
        })
        # make all other columns width 150
        requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize': 150,
                },
                'fields': 'pixelSize',
                'range': {
                    'sheet_id': sheet.id,
                    'dimension': 'COLUMNS',
                    'startIndex': 1,
                },
            }
        })

        # make notes row proper height
        requests.append({
            'updateDimensionProperties': {
                'properties': {
                    'pixelSize':
                        self._template['values']['notesRowHeight'],
                },
                'fields': 'pixelSize',
                'range': {
                    'sheet_id': sheet.id,
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
                    'sheetId': sheet.id,
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

        # add banding (default style white/gray with header and footer)
        header_color = 'bdbdbd'
        color1 = 'ffffff'
        color2 = 'f3f3f3'
        footer_color = 'dedede'

        def hex_to_rgb(hex_color):
            colors = ('red', 'green', 'blue')
            return {
                key: int(hex_color[i:i+2], 16) / 255
                for key, i in zip(colors, range(0, 6, 2))
            }

        requests.append({
            'addBanding': {
                'bandedRange': {
                    'range': {
                        'sheetId': sheet.id,
                        'startColumnIndex': 1,
                    },
                    'rowProperties': {
                        'headerColor': hex_to_rgb(header_color),
                        'firstBandColor': hex_to_rgb(color1),
                        'secondBandColor': hex_to_rgb(color2),
                        'footerColor': hex_to_rgb(footer_color),
                    },
                },
            }
        })

        spreadsheet.batch_update({'requests': requests})

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
                msg = (
                    f'column {col_letter} doesn\'t have a valid '
                    'hyperlink'
                )
                return False, msg

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
            'piece': piece_name,
            'pieceLink': piece_link,
            'sources': sources,
            'comments': comments,
        }
