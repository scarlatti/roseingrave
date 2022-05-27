# Roseingrave

Massively scalable musical source comparator.

## Settings

The `roseingrave.json` file defines alternative names for the input and output
files for some of the commands. The default configuration is:

<!-- prettier-ignore -->
```json
{
  "definitionFiles": {
    "template": ["input", "template_definitions.json"],
    "volunteers": ["input", "volunteer_definitions.json"],
    "pieces": ["input", "piece_definitions.json"]
  },
  "outputs": {
    "spreadsheetsIndex": ["output", "spreadsheets.json"],
    "pieceSummary": ["output", "summary.json"],
    "pieceDataPath": ["output", "data", "by-piece", "{piece}.json"],
    "volunteer_output_folder": ["output", "data", "by-volunteer", "{email}.json"]
  }
}
```

Each value can either be a string for the filename, or an array defining the
path to the file.

In the following, file names/paths will be referenced by its corresponding key.

## Input files

### `"template"`

The `"template"` file defines the names of rows or columns in each created
spreadsheet. It has the following format with default values:

```json
{
  // the email of the person to give ownership of each created spreadsheet
  "owner": "REQUIRED",
  "title": "Title",
  "tempo": "Tempo",
  "key": "Key",
  "keySig": "Key sig.",
  "timeSig": "Time sig.",
  "barCount": "Bars",
  "compass": "Compass",
  "comments": "Comments",
  "notes": "Notes",
  "clefs": "Clefs (if other than G and F)",
  "endOrRepeat": "Endings and Repeat signs",
  "articulation": "Articulation signs",
  "dynamic": "Dynamic signs",
  "hand": "Hand signs",
  "otherIndications": "Other indications"
}
```

Each field will create a row above the bars section, with the exception of the
two following special fields:

- `"columns"`: The right-most column, where comments can be left on any of the
  rows or bars.
- `"notes"`: A single row below the bars section, where source-specific notes
  may be left.

In the future, there will be additional fields for customizing font, font size,
font weight, etc.

## Commands

### `create_sheet`

Create volunteer spreadsheets.

Requires `"piece_definition"`, `"volunteer_definition"`, and
`"template_definition"`. Outputs created spreadsheet links to `"spreadsheets"`.

If any volunteers already exist in `"spreadsheets"`, they will be skipped.

#### Arguments

- `emails` (optional, variadic): The volunteer(s) to create a spreadsheet for.
  If none given, creates spreadsheets for all volunteers found in
  `"volunteer_definition"`.

#### Options

- `--replace`/`-r` (flag): Replace existing volunteer spreadsheets.
- `--new`/`-n` (flag): Create new spreadsheets for all volunteers.
- `-td`: A filename to replace `"template_definition"`.
- `-pd`: A filename to replace `"piece_definition"`.
- `-vd`: A filename to replace `"volunteer_definition"`.

<!-- TODO: following -->

<!--
### `volunteer_summary [EMAIL]`

- creates a volunteer JSON data file for a given volunteer email
  - if no email provided, creates JSONs for all volunteers
- requires `spreadsheets.json` to find the spreadsheet link
  - error if not found
  - maybe use a flag to override the name, like `-s spreadsheets.json`
- outputs `data/by-volunteers/<email>.json`
  - use `data/by-volunteers` as a default output folder and use `-o other_folder` as a way to override
  - see Pathlib to make paths: https://stackoverflow.com/a/50110841/408734

### `piece_summary [PIECE]`

- creates a piece JSON file for a given piece
  - if no piece provided, creates JSONs for all pieces found​
- reads the existing files in the `data/by-pieces/` subdirectory and compiles info from them
  - for accurate summary, run `volunteer_summary` first
  - how to specify if the path name has been changed?
  - does adding options to rename the paths make things too complicated? it's just inelegant to hard-code everything IMHO? thoughts?
- outputs `data/by-pieces/<piece>.json`
  - same remark as for `volunteer_summary` re: output folder flag

### `compile_pieces`

- compiles all piece JSON files into a single file for importing to the master spreadsheet
- reads the existing files in the `data/by-pieces/` subdirectory
  - for accurate summary, run `piece_summary` first
- outputs `summary.json`
  - the format for this file will be a little different from `<piece>.json`, for ease of importing/exporting from the master spreadsheet
  - for example, will include a "summary" field (defaults to `""`) for each source

### `import_master`

- updates the master spreadsheet, or creates it if it doesn't exist in `spreadsheets.json`
- requires `summary.json` and `template_definition.json`
  - for accurate sheet, run `compile_pieces` first
  - this could be issued as a warning with loguru to inform the user
- if created the sheet, updates `spreadsheets.json` with a "MASTER" key and the link

### `export_master`

- exports the master spreadsheet to a JSON file
- requires `spreadsheets.json` (for the spreadsheet link)
  - or `-s other_spreadsheets.json`? is this too bulky?
- outputs/replaces `summary.json` (same as `compile_pieces`)
-->
