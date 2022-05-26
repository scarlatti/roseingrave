# roseingrave

Massively scalable musical source comparator

## Commands

Here is the list of commands that can be run from the command line.

- `create_sheet [EMAIL]`

  - creates a volunteer spreadsheet for a given volunteer email
    - if no email provided, creates spreadsheets for all volunteers in `volunteer_definition.json`
    - if volunteer email already exists in `spreadsheets.json`, skip (don't create another sheet)
      - maybe have a `--force` or `--reset` flag to create a new spreadsheet and replace it in `spreadsheets.json`?
  - requires `piece_definition.json`, `volunteer_definition.json`, and `template_definition.json`
    - maybe these should be default names for arguments that can be specified, i.e., `-p other_piece_definition.json -v other_volunteer_definition.json -t other_template_definition.json`
    - should produce ERROR message (or loguru error) if these files are not findable
  - updates `spreadsheets.json` with a mapping from volunteer email to spreadsheet link

- `volunteer_summary [EMAIL]`

  - creates a volunteer JSON data file for a given volunteer email
    - if no email provided, creates JSONs for all volunteers
  - requires `spreadsheets.json` to find the spreadsheet link
    - error if not found
    - maybe use a flag to override the name, like `-s spreadsheets.json`
  - outputs `data/by-volunteers/<email>.json`
    - use `data/by-volunteers` as a default output folder and use `-o other_folder` as a way to override
    - see Pathlib to make paths: https://stackoverflow.com/a/50110841/408734

- `piece_summary [PIECE]`

  - creates a piece JSON file for a given piece
    - if no piece provided, creates JSONs for all pieces found​
  - reads the existing files in the `data/by-volunteers/` subdirectory and compiles info from them
    - for accurate summary, run `volunteer_summary` first
    - how to specify if the path name has been changed?
    - does adding options to rename the paths make things too complicated? it's just inelegant to hard-code everything IMHO? thoughts?
  - outputs `data/by-pieces/<piece>.json`
    - same remark as for `volunteer_summary` re: output folder flag

- `compile_pieces` (open to name suggestions)
  - compiles all piece JSON files into a single file for importing to the master spreadsheet
  - reads the existing files in the `pieces/` subdirectory
    - for accurate summary, run `piece_summary` first
  - outputs `summary.json` (open to name suggestions) - the format for this file will be a little different from `<piece>.json`, for ease of importing/exporting from the master spreadsheet - for example, will include a "summary" field (defaults to `""`) for each source
    ​
- `import_master`

  - updates the master spreadsheet, or creates it if it doesn't exist in `spreadsheets.json`
  - requires `summary.json` and `template_definition.json`
    - for accurate sheet, run `compile_pieces` first
    - this could be issued as a warning with loguru to inform the user
  - if created the sheet, updates `spreadsheets.json` with a "MASTER" key and the link

- `export_master`
  - exports the master spreadsheet to a JSON file
  - requires `spreadsheets.json` (for the spreadsheet link)
    - or `-s other_spreadsheets.json`? is this too bulky?
  - outputs/replaces `summary.json` (same as `compile_pieces`)

## Template Definitions

The `template_definitions.json` file defines the names of rows or columns in the created spreadsheets.

Required:

- `"owner"`: the email of the person to give ownership of each created spreadsheet

Optional with defaults:

- `"title"`, `"tempo"`, `"key"`, `"keySig"`, `"timeSig"`, `"barCount"`, `"compass"`, `"comments"`, `"notes"`, `"clefs"`, `"endOrRepeat"`, `"articulation"`, `"dynamic"`, `"hand"`, `"otherIndications"`

Each field will create a row in the table, with the exception of the two following special fields:

- `"comments"` contains annotation left on the right-most column, and comments can be left on any of the rows, that will be placed in the corresponding field;
- `"notes"` are source-specific notes left at the bottom of the spreadsheet, that does not appear in columns.

In the future, there will be additional fields for customizing font, font size, font weight, etc.
