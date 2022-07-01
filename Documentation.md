# Documentation

This is the documentation for the `roseingrave` package.

## Sections

- [Settings](#settings-optional)
- [Input files](#input-files)
  - [`"template"`](#template-optional)
  - [`"pieces"`](#pieces)
  - [`"volunteers"`](#volunteers)
- [Output files](#output-files)
  - [`"spreadsheetsIndex"`](#spreadsheetsindex)
  - [`"volunteerDataPath"`](#volunteerdatapath)
  - [`"pieceDataPath"`](#piecedatapath)
  - [`"summary"`](#summary)
- [Commands](#commands)
  - [`reauth`](#reauth)
  - [`fix_input`](#fixinput)
  - [`create_sheet`](#createsheet)
  - [`volunteer_summary`](#volunteersummary)
  - [`piece_summary`](#piecesummary)
  - [`compile_pieces`](#compilepieces)
  - [`import_master`](#importmaster)
  - [`export_master`](#exportmaster)

## Settings (optional)

The `roseingrave.json` settings file defines alternative names for the input and
output files used in the commands. The default configuration can be found
[here](https://github.com/josephlou5/roseingrave/blob/main/src/roseingrave/defaults/roseingrave.json).

If included, this file must be placed in the root folder from where you run the
commands. Its location cannot be customized. All the paths referenced in this
file will also be relative to the current working directory, unless you happen
to provide a detectable absolute path. It is recommended to create a directory
for the runs of this package and stick to it.

Each value can either be a string for the filename or an array defining the
path to the file. (The path segments will be joined by the Python built-in
platform-aware module `pathlib`.)

For `"volunteerDataPath"` and `"pieceDataPath"`, you must use `"{email}"` and
`"{piece}"` respectively in the path exactly once to format the email of the
volunteer and the name of the piece respectively.

In the following, file names/paths will be referenced by its corresponding key.

## Input files

### `"template"` (optional)

The `"template"` file defines the names of rows or columns and other values to
use for created spreadsheets. The default values can be found
[here](https://github.com/josephlou5/roseingrave/blob/main/src/roseingrave/defaults/template_definitions.json).

The `"masterSpreadsheet"` and `"volunteerSpreadsheet"` values define information
for the master and volunteer spreadsheets respectively:

- `"folder"`: The id of the Google Drive folder to save the created
  spreadsheets. A value of `null` means the root folder.
  - A folder id can be found from the link in the address bar while the folder
    is open: `https://drive.google.com/drive/folders/FOLDER_ID`. Be sure to
    remove any unnecessary values after `?`, such as `?resourcekey=`.
- `"title"`: The title of the spreadsheet.
- `"publicAccess"`: The public access of the spreadsheet. It can either be
  `null` (restricted), `"view"`, or `"edit"`. Unknown values will default to
  `null`.
- `"shareWith"`: An array of email addresses to give edit access of the
  spreadsheet to.
- `"resize"`: Whether the headers column and the source columns should be
  resized to fit the content.

For `"volunteerSpreadsheet"` specifically:

- `"title"`: The format of the title, with the format string `"{email}"` (at
  most once) representing the email of the volunteer.
- `"shareWithVolunteer"`: Whether the spreadsheet should be shared with the
  volunteer's email.

Each field under `"metaDataFields"` defines the name of each header, which go in
the rows above the bars section.

Each field under `"validation"` defines specific values that any of the header
fields can take. In particular, a value may be a dropdown with a predefined list
of choices or it may be a checkbox. You must use the corresponding key in
`"metaDataFields"`. To define these, use the following example format:

```json
{
  "validation": {
    "keySig": {
      "type": "dropdown",
      "values": ["C major", "G major", "D major", "A major", "E major"]
    },
    "hand": {
      "type": "checkbox"
    }
  }
}
```

Also see
[`validation_example.json`](https://github.com/josephlou5/roseingrave/blob/main/examples/validation_example.json)
for a larger example.

Each field under `"commentFields"` has the following meaning:

- `"notes"`: The title of the right-most column, where notes can be left on any
  of the headers or bars.
- `"supplementalSources"`: In a piece sheet, the title of a column after
  `"notes"` that lists all the supplemental sources, if any.
- `"comments"`: The title of a single row below the bars section, where
  source-specific comments may be left.
- `"summary"`: In the master spreadsheet, the title of a column for each source
  for a summary of all the volunteer inputs.

Each field under `"values"` has the following meaning:

- `"defaultBarCount"`: If no bar counts are given in `"pieces"`, use this value.
  Must be positive.
- `"commentsRowHeight"`: The number of pixels to make the height of the comments
  row. Must be at least 21 (the default height of a row).

In the future, there will be additional fields for customizing font, font size,
font weight, etc.

### `"pieces"`

The `"pieces"` file defines each piece and the sources for each piece. Each
piece can have an optional link and bar count. Each source requires a name and a
link and also has an optional bar count. The resulting bar section for this
piece will be the max of all the bar counts given, or a default if no bar counts
are given.

Sources may also be supplemental, meaning that they are listed in an additional
column to the right of the `"notes"` column, but don't get their own column in
piece sheets. They will also be ignored when exporting spreadsheets.

The file should have the following format:

```json
[
  {
    "title": "pieceName1",
    "barCount": 50,
    "sources": [
      {
        "name": "sourceName1",
        "link": "sourceLink1",
        "barCount": 100
      }
    ]
  },
  {
    "title": "pieceName2",
    "link": "pieceLink2",
    "sources": [
      {
        "name": "sourceName2",
        "link": "sourceLink2"
      },
      {
        "name": "supplementalSourceName",
        "link": "supplementalSourceLink",
        "supplemental": true
      }
    ]
  }
]
```

Pieces with repeated names will be treated as a single piece with the first link
found and the combination of all their sources. Sources with repeated names will
have the max bar count of the given bar counts and will be marked supplemental
if any of its duplicates are supplemental. Sheets will be created with the order
of the sources preserved.

### `"volunteers"`

The `"volunteers"` file defines each volunteer and the pieces for each
volunteer.

The file should have the following format:

```json
[
  {
    "email": "volunteerEmail",
    "pieces": ["pieceName1", "pieceName2"]
  }
]
```

Volunteers with repeated emails will be treated as a single volunteer with the
combination of all their pieces. Repeated pieces will be ignored after the first
occurrence. Unknown pieces will be ignored. Spreadsheets will be created with
the order of the pieces preserved.

## Output files

### `"spreadsheetsIndex"`

The `"spreadsheetsIndex"` file defines a mapping from volunteer emails to their
corresponding spreadsheet link. It will also have a key of `"MASTER"` for the
master spreadsheet.

### `"volunteerDataPath"`

The `"volunteerDataPath"` template defines a format for the path of files when
exporting volunteer data. It will contain an array of objects representing
pieces.

### `"pieceDataPath"`

The `"pieceDataPath"` template defines a format for the path of files when
exporting piece data. It will contain compiled information about the piece,
including each volunteer-source pair that have matched this piece.

### `"summary"`

The `"summary"` file consolidates all the information about pieces into one file
for ease of importing to and exporting from the master spreadsheet. It has a
very similar format to `"pieceDataPath"` files, except that each source has an
additional field `"summary"`, which is a summary column for each source in the
master spreadsheet.

## Commands

Run `roseingrave --help` or `roseingrave <command> --help` to see commands and
their arguments and options on the command line.

### `reauth`

Reauthenticate the credentials for your OAuth Client.

No options.

### `fix_input`

Fixes input files.

The `"template"` file is not supported because it can get very complex; some
extra options may be due to user error without the user necessarily wanting to
remove them. The user is suggested instead to heed the warnings whenever the
template definitions file is read from in order to fix it.

If a file is not included in `files` but an alternative path is given for it, it
will be ignored.

If there are unresolvable issues, displays warnings and does nothing.

#### Arguments

- `files` (optional, variadic): The files to fix, out of the following options
  (type a list of the options). If none given, all supported files will be
  fixed.
  - `settings`: Remove unknown fields.
  - `pieces`: Combine repeated pieces, keeping the first link found and the max
    bar count found, including bar counts of sources. Combine repeated sources
    for a piece, keeping the first link and the max bar count. Move supplemental
    sources to the end of the list. Move pieces with only supplemental sources
    to the end of the list. Remove pieces with no sources. Remove unknown
    fields.
  - `volunteers`: Combine repeated emails, keeping the union of all sources
    found, preserving order. Remove pieces not found in `"pieces"`. Remove
    volunteers with no pieces. Remove unknown fields.
  - `spreadsheetsIndex`: Sort all keys, with `"MASTER"` (if exists) at the top.
    Remove spreadsheets that are not accessible through the user's account.

#### Options

- `-pd`: A filepath to replace `"pieces"`.
- `-vd`: A filepath to replace `"volunteers"`.
- `-si`: A filepath to replace `"spreadsheetsIndex"`.

### `create_sheet`

Create volunteer spreadsheets.

Requires `"template"`, `"pieces"`, and `"volunteers"`. Outputs created
spreadsheet links to `"spreadsheetsIndex"`.

If any volunteers already exist in `"spreadsheetsIndex"`, they will be skipped.

#### Arguments

- `emails` (optional, variadic): The volunteers to create spreadsheets for.
  If none given, creates spreadsheets for all volunteers found in
  `"volunteers"`.

#### Options

- `-r`/`--replace` (flag): Replace existing volunteer spreadsheets.
  This will not create a new spreadsheet, but will wipe all current content in
  the existing spreadsheet.
- `-n`/`--new` (flag): Create new spreadsheets for all volunteers.
- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-vd`: A filepath to replace `"volunteers"`.
- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `volunteer_summary`

Export volunteer JSON data files.

Requires `"spreadsheetsIndex"` and `"template"`. Outputs created data files to
`"volunteerDataPath"`, replacing existing files.

If the spreadsheets don't match `"template"`, there is undefined behavior. For
proper exported data, ensure that the spreadsheets have the correct format.

#### Arguments

- `emails` (optional, variadic): The volunteers to export data for. If none
  given, exports data for all volunteers found in `"spreadsheetsIndex"`.

#### Options

- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `-td`: A filepath to replace `"template"`.
- `-vdp`: A filepath to replace `"volunteerDataPath"`. Must include `"{email}"`
  exactly once.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `piece_summary`

Export piece JSON data files.

For most accurate summary, run the `volunteer_summary` command first.

Requires `"volunteerDataPath"`, `"template"`, and `"pieces"`. Reads the existing
files in `"volunteerDataPath"`. Outputs created data files to `"pieceDataPath"`,
replacing existing files.

To create the output files, `"template"` and `"pieces"` will be used to
determine the proper keys and bar counts for each source. Unknown pieces and
sources will be skipped. Unknown or missing fields will raise warnings.

#### Arguments

- `pieces` (optional, variadic): The pieces to export data for. If none given,
  exports data for all pieces found when reading the existing files.

#### Options

- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-vdp`: A filepath to replace `"volunteerDataPath"`. Must include `"{email}"`
  exactly once.
- `-pdp`: A filepath to replace `"pieceDataPath"`. Must include `"{piece}"`
  exactly once.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `compile_pieces`

Compile all piece JSON data files into a single file.

For most accurate summary, run the `piece_summary` command first.

Requires `"pieceDataPath"`, `"template"`, and `"pieces"`. Reads the existing
files in `"pieceDataPath"`. Outputs created file to `"summary"`.

To create the output file, `"template"` and `"pieces"` will be used to determine
the proper keys and bar counts for each source. Unknown pieces and sources will
be skipped. Unknown or missing fields will raise warnings.

#### Options

- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-pdp`: A filepath to replace `"pieceDataPath"`. Must include `"{piece}"`
  exactly once.
- `-s`: A filepath to replace `"summary"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `import_master`

Update the master spreadsheet, or create it if it doesn't exist.

Note that this will wipe all current content in the existing spreadsheet. To
keep the original spreadsheet, use the `-c` flag, remove the link from
`"spreadsheetsIndex"`, or make a copy first.

For most accurate sheet, run the `compile_pieces` or `export_master` command
first.

Requires `"spreadsheetsIndex"`, `"template"`, and `"summary"`. If created,
outputs the spreadsheet link to `"spreadsheetsIndex"`.

#### Options

- `-c`/`--create`: Create a new master spreadsheet.
- `-td`: A filepath to replace `"template"`.
- `-pd`: A filepath to replace `"pieces"`.
- `-s`: A filepath to replace `"summary"`.
- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.

### `export_master`

Export the master spreadsheet.

Requires `"spreadsheetsIndex"` and `"template"`. Outputs data to `"summary"`.

If the spreadsheet doesn't match `"template"`, there is undefined behavior. For
proper exported data, ensure that the spreadsheet has the correct format.

#### Options

- `-si`: A filepath to replace `"spreadsheetsIndex"`.
- `-td`: A filepath to replace `"template"`.
- `-s`: A filepath to replace `"summary"`.
- `--strict` (flag): Fail on warnings instead of only displaying them.
